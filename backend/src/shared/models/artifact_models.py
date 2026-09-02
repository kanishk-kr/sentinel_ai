"""
SENTINEL — Artifact Store Database Models (artifacts schema)
Section 5.3 of project.md: artifacts, versions, components, component_sources.
Component-level provenance per FR6.1.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class ArtifactType(str, enum.Enum):
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    CODE = "code"
    PDF = "pdf"
    TEXT = "text"


class ArtifactStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATING = "validating"
    PREVIEW = "preview"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class ComponentType(str, enum.Enum):
    PARAGRAPH = "paragraph"
    CELL = "cell"
    BULLET = "bullet"
    HEADING = "heading"
    TABLE_ROW = "table_row"
    CODE_BLOCK = "code_block"
    IMAGE = "image"
    SLIDE = "slide"


# ── Artifacts (FR6.1) ────────────────────────────────────────
class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = {"schema": "artifacts"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    artifact_type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ArtifactStatus] = mapped_column(Enum(ArtifactStatus), default=ArtifactStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    versions: Mapped[list["ArtifactVersion"]] = relationship(back_populates="artifact", cascade="all, delete-orphan")


# ── Artifact Versions ────────────────────────────────────────
class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = {"schema": "artifacts"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.artifacts.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    generating_model: Mapped[str | None] = mapped_column(String(100))
    verification_verdict_json: Mapped[dict | None] = mapped_column(JSON)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    artifact: Mapped["Artifact"] = relationship(back_populates="versions")
    components: Mapped[list["ArtifactComponent"]] = relationship(
        back_populates="artifact_version", cascade="all, delete-orphan"
    )


# ── Artifact Components (paragraph/cell/bullet level — FR6.1) ─
class ArtifactComponent(Base):
    __tablename__ = "artifact_components"
    __table_args__ = {"schema": "artifacts"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.artifact_versions.id"), nullable=False
    )
    component_type: Mapped[ComponentType] = mapped_column(Enum(ComponentType), nullable=False)
    locator: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "F14", "slide4-bullet2", "para-3"
    content_preview: Mapped[str | None] = mapped_column(Text)
    generated_by_model: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    artifact_version: Mapped["ArtifactVersion"] = relationship(back_populates="components")
    sources: Mapped[list["ArtifactComponentSource"]] = relationship(
        back_populates="component", cascade="all, delete-orphan"
    )


# ── Component Sources (provenance — links component to source doc/page/bbox) ─
class ArtifactComponentSource(Base):
    __tablename__ = "artifact_component_sources"
    __table_args__ = {"schema": "artifacts"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.artifact_components.id"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_document_title: Mapped[str | None] = mapped_column(String(500))
    page_number: Mapped[int | None] = mapped_column(Integer)
    bbox_json: Mapped[dict | None] = mapped_column(JSON)
    chunk_text_preview: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Integer)  # 0.0 to 1.0

    # Relationships
    component: Mapped["ArtifactComponent"] = relationship(back_populates="sources")
