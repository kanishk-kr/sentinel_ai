"""
SENTINEL — Knowledge Store Database Models (kb schema)
Section 5.2 of project.md: kb_documents, document_extractions.
Qdrant handles the vector store separately.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class AccessTagStatus(str, enum.Enum):
    PENDING_ADMIN_REVIEW = "pending_admin_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class RegionType(str, enum.Enum):
    TEXT = "text"
    TABLE = "table"
    DIAGRAM = "diagram"
    HANDWRITING = "handwriting"
    PHOTO = "photo"


class ExtractionMethod(str, enum.Enum):
    OCR = "ocr"
    VISION_LLM = "vision_llm"
    TABLE_PARSER = "table_parser"
    HYBRID = "hybrid"


# ── Knowledge Base Documents ──────────────────────────────────
class KBDocument(Base):
    __tablename__ = "kb_documents"
    __table_args__ = {"schema": "kb"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf, docx, xlsx, image, etc.
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer)
    access_tag: Mapped[str] = mapped_column(String(100), default="unclassified", index=True)
    access_tag_status: Mapped[AccessTagStatus] = mapped_column(
        Enum(AccessTagStatus), default=AccessTagStatus.PENDING_ADMIN_REVIEW
    )
    classified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Admin who confirmed tag
    classification_notes: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    processing_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    extractions: Mapped[list["DocumentExtraction"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


# ── Document Extractions (FR4.1 — region-level) ──────────────
class DocumentExtraction(Base):
    __tablename__ = "document_extractions"
    __table_args__ = {"schema": "kb"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kb.kb_documents.id"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    region_type: Mapped[RegionType] = mapped_column(Enum(RegionType), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(200))
    field_value: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    evidence_confidence_json: Mapped[dict | None] = mapped_column(JSON)
    # Multi-factor confidence: {ocr_quality, source_certainty, extraction_consistency, verifier_agreement}
    bbox_json: Mapped[dict | None] = mapped_column(JSON)  # {x1, y1, x2, y2}
    method: Mapped[ExtractionMethod] = mapped_column(Enum(ExtractionMethod), nullable=False)
    conflict_notes: Mapped[str | None] = mapped_column(Text)  # Evidence Resolver conflict flags
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["KBDocument"] = relationship(back_populates="extractions")
