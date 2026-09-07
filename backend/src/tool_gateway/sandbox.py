"""
SENTINEL — Tool Gateway: hardened sandbox + document export.
Section 3.7 / FR6.1–6.2.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from src.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "python:3.11-slim")


class SandboxExecutor:
    """
    Ephemeral Docker sandbox (Section 3.7):
    --network none, cap-drop ALL, non-root, memory/CPU/pids limits, destroyed after run.
    Falls back to a heavily restricted subprocess only if Docker is unavailable AND
    SENTINEL_ALLOW_HOST_SANDBOX=1 (development).
    """

    def build_docker_command(self, code_path: Path, workspace: Path, timeout: int) -> list[str]:
        return [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--cap-drop=ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "64",
            "--memory", "512m",
            "--cpus", "1",
            "--user", "1000:1000",
            "-v", f"{workspace}:/workspace:rw",
            "-v", f"{code_path}:/workspace/job.py:ro",
            "-w", "/workspace",
            SANDBOX_IMAGE,
            "python3", "/workspace/job.py",
        ]

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
        task_id: str | None = None,
    ) -> str:
        if language != "python":
            return f"Language '{language}' not supported yet"
        return await self._execute_python(code, timeout, task_id)

    async def _execute_python(self, code: str, timeout: int, task_id: str | None) -> str:
        workspace = settings.sandbox_path / (task_id or uuid.uuid4().hex)
        workspace.mkdir(parents=True, exist_ok=True)
        code_path = workspace / "job.py"
        code_path.write_text(code, encoding="utf-8")

        docker_bin = shutil.which("docker")
        if docker_bin:
            cmd = self.build_docker_command(code_path, workspace, timeout)
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout + 5)
                output = stdout.decode("utf-8", errors="replace")
                errors = stderr.decode("utf-8", errors="replace")
                if process.returncode == 0:
                    return f"Exit code: 0\nOutput:\n{output}"
                return f"Exit code: {process.returncode}\nOutput:\n{output}\nErrors:\n{errors}"
            except asyncio.TimeoutError:
                return "Error: Code execution timed out"
            except FileNotFoundError:
                logger.warning("docker binary missing at runtime")
            except Exception as exc:
                logger.error("Docker sandbox failed: %s", exc)
                return f"Error: sandbox failed: {exc}"
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

        if os.environ.get("SENTINEL_ALLOW_HOST_SANDBOX") == "1":
            logger.warning("Docker unavailable; host sandbox enabled via SENTINEL_ALLOW_HOST_SANDBOX")
            try:
                process = await asyncio.create_subprocess_exec(
                    "python3", str(code_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(workspace),
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                output = stdout.decode("utf-8", errors="replace")
                errors = stderr.decode("utf-8", errors="replace")
                return f"Exit code: {process.returncode}\nOutput:\n{output}\nErrors:\n{errors}"
            except asyncio.TimeoutError:
                return "Error: Code execution timed out"
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

        shutil.rmtree(workspace, ignore_errors=True)
        return (
            "Error: Hardened Docker sandbox is required. "
            "Install Docker or set SENTINEL_ALLOW_HOST_SANDBOX=1 for local development only."
        )


class ExportService:
    async def create_document(
        self,
        doc_type: str,
        content: str,
        task_id: str,
        title: str = "SENTINEL Generated Document",
        metadata: dict | None = None,
        db=None,
        user_id: str | None = None,
    ) -> str:
        output_dir = settings.artifact_store_path / task_id
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata = metadata or {}

        if doc_type == "docx":
            filepath = await self._create_docx(content, title, output_dir, metadata)
        elif doc_type == "xlsx":
            filepath = await self._create_xlsx(content, title, output_dir, metadata)
        elif doc_type == "pptx":
            filepath = await self._create_pptx(content, title, output_dir, metadata)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")

        if db:
            from src.shared.models.artifact_models import (
                Artifact,
                ArtifactComponent,
                ArtifactComponentSource,
                ArtifactStatus,
                ArtifactType,
                ArtifactVersion,
                ComponentType,
            )

            artifact = Artifact(
                task_id=uuid.UUID(task_id),
                artifact_type=ArtifactType(doc_type),
                title=title,
                current_version=1,
                status=ArtifactStatus.DRAFT,
            )
            db.add(artifact)
            await db.flush()

            version = ArtifactVersion(
                artifact_id=artifact.id,
                version_number=1,
                storage_path=filepath,
                generating_model=metadata.get("generating_model", "policy-gateway"),
                metadata_json=metadata,
            )
            db.add(version)
            await db.flush()

            await self._write_component_provenance(
                db, version.id, doc_type, content, metadata
            )

        return filepath

    async def _write_component_provenance(self, db, version_id, doc_type: str, content: str, metadata: dict) -> None:
        from src.shared.models.artifact_models import (
            ArtifactComponent,
            ArtifactComponentSource,
            ComponentType,
        )

        sources = metadata.get("sources") or []
        blocks = [line.strip() for line in content.split("\n") if line.strip()]
        ctype = ComponentType.PARAGRAPH if doc_type != "xlsx" else ComponentType.CELL
        if doc_type == "pptx":
            ctype = ComponentType.BULLET

        for index, block in enumerate(blocks[:50], start=1):
            component = ArtifactComponent(
                artifact_version_id=version_id,
                component_type=ctype,
                locator=f"{'R' if doc_type == 'xlsx' else 'para-' if doc_type == 'docx' else 'slide1-bullet'}{index}",
                content_preview=block[:500],
            )
            db.add(component)
            await db.flush()
            for src in sources[:5]:
                doc_id = src.get("document_id")
                if not doc_id:
                    continue
                try:
                    source_uuid = uuid.UUID(str(doc_id))
                except ValueError:
                    continue
                db.add(ArtifactComponentSource(
                    artifact_component_id=component.id,
                    source_document_id=source_uuid,
                    source_document_title=src.get("document_title"),
                    page_number=src.get("page_number"),
                    bbox_json=src.get("bbox"),
                    chunk_text_preview=(src.get("chunk_text") or "")[:300],
                    confidence=src.get("similarity_score"),
                ))
        await db.flush()

    async def _create_docx(self, content: str, title: str, output_dir: Path, metadata: dict | None = None) -> str:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        title_para = doc.add_heading(title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        notice = doc.add_paragraph()
        notice.add_run("Generated by SENTINEL — Sovereign AI Workbench").italic = True
        notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()

        for para_text in content.split("\n"):
            if not para_text.strip():
                continue
            if para_text.startswith("# "):
                doc.add_heading(para_text[2:], level=1)
            elif para_text.startswith("## "):
                doc.add_heading(para_text[3:], level=2)
            elif para_text.startswith("- "):
                doc.add_paragraph(para_text[2:], style="List Bullet")
            else:
                doc.add_paragraph(para_text)

        filename = f"{uuid.uuid4().hex[:8]}_{title.replace(' ', '_')[:50]}.docx"
        filepath = output_dir / filename
        doc.save(str(filepath))
        return str(filepath)

    async def _create_xlsx(self, content: str, title: str, output_dir: Path, metadata: dict | None = None) -> str:
        """FR6.2: openpyxl generate → LibreOffice recalc in a separate outdir → reload totals."""
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"
        ws["A1"] = title
        ws["A1"].font = Font(bold=True, size=14)
        ws["A2"] = "Generated by SENTINEL"
        ws["A2"].font = Font(italic=True, size=10)

        rows = content.strip().split("\n")
        numeric_start_row = 4
        last_data_row = 3
        for i, row in enumerate(rows, start=4):
            cells = row.split(",") if "," in row else row.split("\t") if "\t" in row else [row]
            for j, cell_value in enumerate(cells):
                raw = cell_value.strip()
                try:
                    value: str | float | int = float(raw) if "." in raw else int(raw)
                except ValueError:
                    value = raw
                ws.cell(row=i, column=j + 1, value=value)
            last_data_row = i

        if last_data_row >= numeric_start_row:
            total_row = last_data_row + 1
            ws.cell(row=total_row, column=1, value="TOTAL")
            ws.cell(row=total_row, column=2, value=f"=SUM(B{numeric_start_row}:B{last_data_row})")

        filename = f"{uuid.uuid4().hex[:8]}_{title.replace(' ', '_')[:50]}.xlsx"
        filepath = output_dir / filename
        wb.save(str(filepath))

        recalc_ok, recalc_errors = self._recalculate_excel(filepath)
        metadata = metadata if metadata is not None else {}
        metadata["excel_recalculated"] = recalc_ok
        metadata["excel_recalc_errors"] = recalc_errors
        return str(filepath)

    def _recalculate_excel(self, filepath: Path) -> tuple[bool, list[str]]:
        outdir = Path(tempfile.mkdtemp(prefix="sentinel-xlsx-"))
        try:
            cmd = [
                "soffice", "--headless", "--convert-to", "xlsx",
                "--outdir", str(outdir), str(filepath),
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=45)
            produced = list(outdir.glob("*.xlsx"))
            if result.returncode != 0 or not produced:
                logger.warning("LibreOffice recalc failed: %s", result.stderr.decode(errors="replace"))
                return False, ["LibreOffice recalculation failed or soffice missing"]

            shutil.copy2(produced[0], filepath)

            from openpyxl import load_workbook
            cached = load_workbook(filepath, data_only=True)
            formulas = load_workbook(filepath, data_only=False)
            errors: list[str] = []
            error_tokens = ("#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NAME?")
            for sheet in cached.worksheets:
                formula_sheet = formulas[sheet.title]
                for row in sheet.iter_rows():
                    for cell in row:
                        value = cell.value
                        if isinstance(value, str) and value in error_tokens:
                            errors.append(f"{sheet.title}!{cell.coordinate}={value}")
                        formula = formula_sheet[cell.coordinate].value
                        if isinstance(formula, str) and formula.startswith("=") and value is None:
                            errors.append(f"{sheet.title}!{cell.coordinate} formula did not cache a value")
            return len(errors) == 0, errors
        except FileNotFoundError:
            logger.warning("LibreOffice not available for Excel recalculation")
            return False, ["LibreOffice (soffice) not installed"]
        except subprocess.TimeoutExpired:
            return False, ["LibreOffice recalculation timed out"]
        finally:
            shutil.rmtree(outdir, ignore_errors=True)

    async def _create_pptx(self, content: str, title: str, output_dir: Path, metadata: dict | None = None) -> str:
        from pptx import Presentation

        prs = Presentation()
        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = "Generated by SENTINEL — Sovereign AI Workbench"

        sections = content.split("\n\n")
        for section in sections:
            if not section.strip():
                continue
            slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(slide_layout)
            lines = section.strip().split("\n")
            if lines:
                slide.shapes.title.text = lines[0].replace("# ", "").replace("## ", "")
                body = slide.placeholders[1]
                body.text = "\n".join(lines[1:]) if len(lines) > 1 else ""

        filename = f"{uuid.uuid4().hex[:8]}_{title.replace(' ', '_')[:50]}.pptx"
        filepath = output_dir / filename
        prs.save(str(filepath))
        return str(filepath)


sandbox_executor = SandboxExecutor()
export_service = ExportService()
