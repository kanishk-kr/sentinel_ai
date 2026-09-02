"""
SENTINEL — Audit Store Database Models (audit schema)
Section 5.4 of project.md: audit_log, audit_checkpoints, network_events.
Hash-chained, sequence-numbered, append-only (FR7.6).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


# ── Audit Log (hash-chained, sequence-numbered — FR7.6) ──────
class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "audit"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Types: auth, policy_decision, model_invoke, tool_exec, rag_query, artifact_create,
    #        approval_decision, mode_change, system_event
    actor: Mapped[str] = mapped_column(String(200), nullable=False)  # user_id or service_id
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(500))
    model_or_tool: Mapped[str | None] = mapped_column(String(100))
    input_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of input (never raw content)
    output_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of output
    policy_decision_json: Mapped[dict | None] = mapped_column(JSON)
    risk_tier: Mapped[str | None] = mapped_column(String(10))
    allowed: Mapped[bool | None] = mapped_column(Boolean)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Hash of previous entry
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256(prev_hash || payload_metadata)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Audit Checkpoints (periodic signed checkpoints) ──────────
class AuditCheckpoint(Base):
    __tablename__ = "audit_checkpoints"
    __table_args__ = {"schema": "audit"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    up_to_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text)  # Optional signed checkpoint
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Network Events (independent monitor — FR7.5) ─────────────
class NetworkEvent(Base):
    __tablename__ = "network_events"
    __table_args__ = {"schema": "audit"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_process: Mapped[str | None] = mapped_column(String(200))
    source_container: Mapped[str | None] = mapped_column(String(200))
    dest_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dest_port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(10), default="tcp")
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rule_matched: Mapped[str | None] = mapped_column(String(200))
    payload_size_bytes: Mapped[int | None] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
