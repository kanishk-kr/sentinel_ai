"""
SENTINEL — Operational Database Models (ops schema)
Section 5.1 of project.md: users, sessions, messages, agent_*, approvals, model_registry.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


# ── Enums ─────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"


class AgentStepStatus(str, enum.Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    COMMITTED = "COMMITTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    VERIFY_FAILED = "VERIFY_FAILED"


class TaskStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RiskTier(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ApprovalDecision(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ── Users ─────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    access_tags: Mapped[dict | None] = mapped_column(JSON, default=list)  # Tags user can access for RAG
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ── Sessions ──────────────────────────────────────────────────
class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), default="New Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")


# ── Messages ──────────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100))
    evidence_confidence_json: Mapped[dict | None] = mapped_column(JSON)
    citations: Mapped[list | None] = mapped_column(JSON)  # [{source, page, bbox, confidence}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session: Mapped["Session"] = relationship(back_populates="messages")


# ── Agent Tasks (FR3.2 — capability-scoped execution) ────────
class AgentTask(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.sessions.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.users.id"), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.QUEUED)
    plan_json: Mapped[dict | None] = mapped_column(JSON)  # Decomposed plan from Planner
    execution_context_json: Mapped[dict | None] = mapped_column(JSON)  # Capability-scoped context
    attachments: Mapped[list | None] = mapped_column(JSON)  # File IDs
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    steps: Mapped[list["AgentStep"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    checkpoints: Mapped[list["AgentCheckpoint"]] = relationship(back_populates="task", cascade="all, delete-orphan")


# ── Agent Steps (FR3.3 — idempotent commit-state machine) ────
class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("operation_id", name="uq_agent_steps_operation_id"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.agent_tasks.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tool_used: Mapped[str | None] = mapped_column(String(100))
    model_used: Mapped[str | None] = mapped_column(String(100))
    risk_tier: Mapped[RiskTier] = mapped_column(Enum(RiskTier), default=RiskTier.LOW)
    status: Mapped[AgentStepStatus] = mapped_column(Enum(AgentStepStatus), default=AgentStepStatus.PENDING)
    operation_id: Mapped[str | None] = mapped_column(String(200))  # {task_id}-{step_id} idempotency key
    input_hash: Mapped[str | None] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64))
    result_json: Mapped[dict | None] = mapped_column(JSON)
    verification_verdict_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    task: Mapped["AgentTask"] = relationship(back_populates="steps")
    events: Mapped[list["AgentEvent"]] = relationship(back_populates="step", cascade="all, delete-orphan")


# ── Agent Events (fine-grained log per step) ──────────────────
class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.agent_steps.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    step: Mapped["AgentStep"] = relationship(back_populates="events")


# ── Agent Checkpoints (cheap resume point — FR3.4) ────────────
class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.agent_tasks.id"), nullable=False)
    last_committed_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.agent_steps.id"))
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task: Mapped["AgentTask"] = relationship(back_populates="checkpoints")


# ── Approvals (FR3.6 — human approval for HIGH-risk) ─────────
class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.agent_steps.id"))
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # FK added in artifact models
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.users.id"), nullable=False)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.users.id"))
    decision: Mapped[ApprovalDecision] = mapped_column(Enum(ApprovalDecision), default=ApprovalDecision.PENDING)
    risk_tier: Mapped[RiskTier] = mapped_column(Enum(RiskTier), default=RiskTier.HIGH)
    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Model Registry (FR1.1, FR2.2) ────────────────────────────
class ModelRegistry(Base):
    __tablename__ = "model_registry"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # groq, gemini, ollama, vllm
    backend: Mapped[str] = mapped_column(String(50), nullable=False)  # api, ollama, vllm
    runtime_target: Mapped[str] = mapped_column(String(200), nullable=False)  # API model name or Docker service
    capabilities_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    requirements_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, nullable=False)
    approx_vram_gb: Mapped[float | None] = mapped_column(Integer)  # For local models
    latency_class: Mapped[str] = mapped_column(String(20), default="medium")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    model_hash: Mapped[str | None] = mapped_column(String(64))
    model_signature: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[str | None] = mapped_column(String(50))
    approved_by: Mapped[str | None] = mapped_column(String(100))
    import_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Job Queue (Postgres-based — Section 2.2) ─────────────────
class JobQueue(Base):
    __tablename__ = "job_queue"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.agent_tasks.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    priority: Mapped[int] = mapped_column(Integer, default=0)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
