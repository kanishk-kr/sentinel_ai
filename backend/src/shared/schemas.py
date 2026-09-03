"""
SENTINEL — Pydantic Schemas for API Contracts
Covers all endpoints from Section 4 of project.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════
# Auth Schemas
# ══════════════════════════════════════════════════════════════
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str
    password: str = Field(..., min_length=6)
    role: str = "viewer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# Session Schemas
# ══════════════════════════════════════════════════════════════
class SessionCreate(BaseModel):
    title: str = "New Chat"


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


# ══════════════════════════════════════════════════════════════
# Message Schemas
# ══════════════════════════════════════════════════════════════
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    attachments: list[str] | None = None  # File IDs


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    model_used: str | None = None
    evidence_confidence_json: dict | None = None
    citations: list[dict] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# Task Schemas (FR3.2, FR3.5, FR9.5)
# ══════════════════════════════════════════════════════════════
class TaskCreate(BaseModel):
    goal: str = Field(..., min_length=1)
    attachments: list[str] | None = None  # File IDs
    session_id: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    status: str


class TaskDetailResponse(BaseModel):
    id: str
    goal: str
    status: str
    plan: dict | None = None
    execution_context: dict | None = None
    steps: list["StepResponse"] = []
    last_committed_step: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StepResponse(BaseModel):
    id: str
    step_order: int
    description: str
    tool_used: str | None = None
    model_used: str | None = None
    risk_tier: str
    status: str
    operation_id: str | None = None
    verification_verdict: dict | None = None
    result: dict | str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# WebSocket Events (FR9.5)
# ══════════════════════════════════════════════════════════════
class WSEvent(BaseModel):
    task_id: str
    step_id: str | None = None
    event: str  # step_started, tool_execution, model_invoke, awaiting_approval, completed, error
    tool: str | None = None
    model: str | None = None
    status: str | None = None
    risk_tier: str | None = None
    artifact_id: str | None = None
    audit_id: str | None = None
    message: str | None = None
    progress: float | None = None  # 0.0 to 1.0
    timestamp: datetime = Field(default_factory=datetime.now)


# ══════════════════════════════════════════════════════════════
# File Upload Schemas
# ══════════════════════════════════════════════════════════════
class FileUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    access_tag: str
    access_tag_status: str
    processing_status: str


class FileDetailResponse(BaseModel):
    id: str
    title: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    page_count: int | None = None
    access_tag: str
    access_tag_status: str
    chunk_count: int
    processing_status: str
    extractions: list["ExtractionResponse"] = []
    ingested_at: datetime

    model_config = {"from_attributes": True}


class ExtractionResponse(BaseModel):
    id: str
    page_number: int
    region_type: str
    field_name: str | None = None
    field_value: str | None = None
    evidence_confidence: dict | None = None
    bbox: dict | None = None
    method: str

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# Document Classification (Admin — FR5.1)
# ══════════════════════════════════════════════════════════════
class ClassifyDocumentRequest(BaseModel):
    access_tag: str = Field(..., min_length=1)
    notes: str | None = None


# ══════════════════════════════════════════════════════════════
# RAG Query Schemas (FR5.2)
# ══════════════════════════════════════════════════════════════
class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    filter_tags: list[str] | None = None  # Additional tag filters


class RAGChunkResult(BaseModel):
    document_id: str
    document_title: str
    chunk_text: str
    page_number: int | None = None
    access_tag: str
    similarity_score: float
    evidence_confidence: dict | None = None


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    model_used: str
    chunks: list[RAGChunkResult]
    citations: list[dict]
    evidence_confidence: dict  # Multi-factor breakdown (FR4.3)
    verified: bool


# ══════════════════════════════════════════════════════════════
# Artifact Schemas (FR6)
# ══════════════════════════════════════════════════════════════
class ArtifactResponse(BaseModel):
    id: str
    task_id: str
    artifact_type: str
    title: str
    current_version: int
    status: str
    versions: list["ArtifactVersionResponse"] = []
    provenance: list["ProvenanceResponse"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ArtifactVersionResponse(BaseModel):
    id: str
    version_number: int
    storage_path: str
    generating_model: str | None = None
    verification_verdict: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProvenanceResponse(BaseModel):
    component_type: str
    locator: str
    content_preview: str | None = None
    sources: list["SourceResponse"] = []


class SourceResponse(BaseModel):
    source_document_title: str | None = None
    page_number: int | None = None
    bbox: dict | None = None
    confidence: float | None = None


class ArtifactApproveRequest(BaseModel):
    comment: str | None = None


# ══════════════════════════════════════════════════════════════
# Approval Schemas (FR3.6)
# ══════════════════════════════════════════════════════════════
class ApprovalResponse(BaseModel):
    id: str
    task_step_id: str | None = None
    artifact_id: str | None = None
    requested_by: str
    approver_id: str | None = None
    decision: str
    risk_tier: str
    action_description: str
    comment: str | None = None
    decided_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    comment: str | None = None


# ══════════════════════════════════════════════════════════════
# Audit Schemas (FR7.6)
# ══════════════════════════════════════════════════════════════
class AuditLogResponse(BaseModel):
    id: str
    sequence_number: int
    entry_type: str
    actor: str
    action: str
    model_or_tool: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    allowed: bool | None = None
    risk_tier: str | None = None
    entry_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditVerifyResponse(BaseModel):
    entries_verified: int
    chain_integrity: str  # PASS or FAIL
    missing_sequences: int
    hash_mismatches: int
    last_checkpoint_sequence: int | None = None
    last_checkpoint_valid: bool | None = None


# ══════════════════════════════════════════════════════════════
# Security / Network Monitor Schemas (FR7.5)
# ══════════════════════════════════════════════════════════════
class NetworkEventResponse(BaseModel):
    id: str
    source_process: str | None = None
    source_container: str | None = None
    dest_ip: str
    dest_port: int
    protocol: str
    allowed: bool
    timestamp: datetime

    model_config = {"from_attributes": True}


class SecurityModeResponse(BaseModel):
    current_mode: str  # "sovereign" or "controlled"
    sovereign_mode: bool
    internet_status: str  # "blocked" or "restricted"
    banner_text: str
    last_changed: datetime | None = None


class SecurityModeChangeRequest(BaseModel):
    mode: str = Field(..., pattern="^(sovereign|controlled)$")
    admin_password: str  # Separately authenticated (FR7.2)


# ══════════════════════════════════════════════════════════════
# Model Schemas (FR1)
# ══════════════════════════════════════════════════════════════
class ModelInfoResponse(BaseModel):
    id: str
    model_id: str
    display_name: str
    provider: str
    backend: str
    capabilities: dict
    requirements: dict
    context_window: int
    latency_class: str
    active: bool
    state: str = "AVAILABLE"  # For API models: AVAILABLE; for local: UNLOADED/LOADING/RESIDENT/etc.
    approx_vram_gb: float | None = None

    model_config = {"from_attributes": True}


class ModelRegisterRequest(BaseModel):
    model_id: str
    display_name: str
    provider: str
    backend: str
    runtime_target: str
    capabilities: dict
    requirements: dict
    context_window: int
    latency_class: str = "medium"
    approx_vram_gb: float | None = None


class RoutingResult(BaseModel):
    status: str  # "OK" or "ROUTING_FAILURE"
    model_id: str | None = None
    reason: list[str] = []
    confidence: float | None = None
    unmet_requirements: list[str] | None = None


# ══════════════════════════════════════════════════════════════
# Capability-Scoped Execution Context (FR3.2)
# ══════════════════════════════════════════════════════════════
class CapabilityScopedContext(BaseModel):
    task_id: str
    user: str
    user_role: str
    allowed_tools: list[str] = []
    allowed_paths: list[str] = []
    network: str = "none"  # "none" or "controlled"
    max_iterations: int = 10
    max_runtime_seconds: int = 300
    allowed_models: list[str] = []
    trust_boundary: str = "sovereign"


# ══════════════════════════════════════════════════════════════
# Verification Layer (FR3.7)
# ══════════════════════════════════════════════════════════════
class VerificationVerdict(BaseModel):
    status: str  # "PASS" or "FAILED"
    checks: dict = {}  # {schema, citations, evidence_support, domain_validation}
    errors: list[str] = []
    warnings: list[str] = []


# ══════════════════════════════════════════════════════════════
# Policy Gateway Schemas
# ══════════════════════════════════════════════════════════════
class PolicyDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    risk_tier: str = "LOW"
    requires_approval: bool = False
    approval_id: str | None = None


# ══════════════════════════════════════════════════════════════
# Dashboard / Home Schemas
# ══════════════════════════════════════════════════════════════
class DashboardResponse(BaseModel):
    sovereignty_mode: str
    active_tasks: int
    pending_approvals: int
    total_documents: int
    total_artifacts: int
    total_models: int
    recent_audit_entries: int
    network_events_blocked: int
    system_health: str  # "healthy", "degraded", "error"
