"""
SENTINEL — Document Intelligence pipeline (FR4.1 / FR4.2).
Scanned PDF → region classifier → OCR + Vision → Evidence Resolver → chunks.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_service.rag import document_classifier, evidence_resolver, rag_service
from src.shared.models import DocumentExtraction, ExtractionMethod, KBDocument, RegionType

logger = logging.getLogger(__name__)


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if not text:
        return []
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def _ocr_image(image) -> tuple[str, float]:
    try:
        import pytesseract
        from pytesseract import Output

        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        words = []
        confs = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            if text and str(text).strip():
                words.append(text)
                try:
                    confs.append(float(conf))
                except (TypeError, ValueError):
                    pass
        avg = (sum(confs) / len(confs) / 100.0) if confs else 0.4
        return " ".join(words).strip(), round(avg, 3)
    except Exception as exc:
        logger.warning("pytesseract OCR failed: %s", exc)
        return "", 0.0


def _render_pdf_pages(file_path: Path) -> list:
    try:
        from pdf2image import convert_from_path
        return convert_from_path(str(file_path), dpi=150)
    except Exception as exc:
        logger.warning("pdf2image failed (poppler missing?): %s", exc)
        return []


def _image_bytes(image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


async def ingest_document_pipeline(doc: KBDocument, db: AsyncSession) -> int:
    file_path = Path(doc.source_path)
    if not file_path.exists():
        raise FileNotFoundError(doc.source_path)

    page_images = []
    embedded_pages: list[str] = []

    if doc.file_type == "pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(file_path))
            doc.page_count = len(reader.pages)
            for page in reader.pages:
                embedded_pages.append(page.extract_text() or "")
        except Exception:
            embedded_pages = []
        page_images = _render_pdf_pages(file_path)
        if not doc.page_count:
            doc.page_count = len(page_images) or len(embedded_pages)
    elif doc.file_type in ("png", "jpg", "jpeg", "tif", "tiff", "webp"):
        from PIL import Image
        page_images = [Image.open(file_path)]
        doc.page_count = 1
    elif doc.file_type in ("txt", "md", "csv"):
        text_content = file_path.read_text(errors="ignore")
        chunks = _chunk_text(text_content)
        chunk_dicts = [{"text": c, "title": doc.title, "page_number": 1} for c in chunks]
        return await rag_service.ingest_document(str(doc.id), chunk_dicts, doc.access_tag, db)
    elif doc.file_type == "docx":
        from docx import Document as Docx
        text_content = "\n".join(p.text for p in Docx(str(file_path)).paragraphs)
        chunks = _chunk_text(text_content)
        chunk_dicts = [{"text": c, "title": doc.title, "page_number": 1} for c in chunks]
        return await rag_service.ingest_document(str(doc.id), chunk_dicts, doc.access_tag, db)

    all_text_parts: list[str] = []
    page_count = max(len(page_images), len(embedded_pages), 1)

    for page_number in range(1, page_count + 1):
        embedded = embedded_pages[page_number - 1] if page_number - 1 < len(embedded_pages) else ""
        image = page_images[page_number - 1] if page_number - 1 < len(page_images) else None

        ocr_text, ocr_conf = ("", 0.0)
        regions = [{"region_type": "text", "bbox": None, "confidence": 0.5}]
        vision_text = ""

        if image is not None:
            image_bytes = _image_bytes(image)
            regions = await document_classifier.classify_page_regions(image_bytes, page_number)
            ocr_text, ocr_conf = _ocr_image(image)
            needs_vision = any(
                str(r.get("region_type", "")).lower() in ("diagram", "handwriting", "photo", "table")
                for r in regions
            )
            if needs_vision or len((embedded or "").strip()) < 40:
                try:
                    from src.model_gateway.execution_manager import execution_manager
                    from src.model_gateway.router import model_router

                    routing = model_router.route({
                        "capabilities": ["vision", "ocr_assist"],
                        "vision": True,
                        "min_context": 4096,
                    })
                    if routing.status == "OK":
                        vision_text = await execution_manager.invoke_vision(
                            model_id=routing.model_id,
                            prompt="Extract all readable text, table cells, and a short description of diagrams from this page. Return plain text.",
                            image_data=image_bytes,
                        )
                except Exception as exc:
                    logger.warning("Vision extraction failed: %s", exc)

        ocr_extractions = []
        if ocr_text:
            ocr_extractions.append({
                "field_name": "page_text",
                "field_value": ocr_text,
                "confidence": ocr_conf,
            })
        elif embedded.strip():
            ocr_extractions.append({
                "field_name": "page_text",
                "field_value": embedded,
                "confidence": 0.85,
            })

        vision_extractions = []
        if vision_text:
            vision_extractions.append({
                "field_name": "page_text",
                "field_value": vision_text,
                "confidence": 0.75,
            })

        resolved = evidence_resolver.resolve(ocr_extractions, vision_extractions, page_number)
        primary_region = str((regions[0].get("region_type") if regions else "text") or "text").lower()
        region_enum = {
            "text": RegionType.TEXT,
            "table": RegionType.TABLE,
            "diagram": RegionType.DIAGRAM,
            "handwriting": RegionType.HANDWRITING,
            "photo": RegionType.PHOTO,
        }.get(primary_region, RegionType.TEXT)

        for field in resolved:
            method_name = field.get("method", "ocr")
            method = {
                "ocr": ExtractionMethod.OCR,
                "vision_llm": ExtractionMethod.VISION_LLM,
                "hybrid": ExtractionMethod.HYBRID,
            }.get(method_name, ExtractionMethod.OCR)
            db.add(DocumentExtraction(
                document_id=doc.id,
                page_number=page_number,
                region_type=region_enum,
                field_name=field.get("field_name"),
                field_value=field.get("field_value"),
                raw_text=field.get("field_value"),
                evidence_confidence_json=field.get("evidence_confidence"),
                bbox_json=field.get("bbox"),
                method=method,
                conflict_notes=field.get("conflict_notes"),
            ))
            if field.get("field_value"):
                all_text_parts.append(f"--- Page {page_number} ---\n{field['field_value']}")

        if not resolved:
            fallback = embedded or ocr_text or vision_text
            if fallback:
                all_text_parts.append(f"--- Page {page_number} ---\n{fallback}")

    text_content = "\n".join(all_text_parts)
    chunks = _chunk_text(text_content)
    chunk_dicts = [{"text": c, "title": doc.title, "page_number": i + 1} for i, c in enumerate(chunks)]
    ingested = await rag_service.ingest_document(str(doc.id), chunk_dicts, doc.access_tag, db)
    await db.flush()
    return ingested
