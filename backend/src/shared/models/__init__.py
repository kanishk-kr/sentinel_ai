"""
SENTINEL — Database Models Registry
Imports all models so SQLAlchemy's metadata.create_all() discovers them.
"""
from src.shared.models.ops_models import (
    AgentCheckpoint,
    AgentEvent,
    AgentStep,
    AgentStepStatus,
    AgentTask,
    Approval,
    ApprovalDecision,
    JobQueue,
    Message,
    ModelRegistry,
    RiskTier,
    Session,
    TaskStatus,
    User,
    UserRole,
)
from src.shared.models.kb_models import (
    AccessTagStatus,
    DocumentExtraction,
    ExtractionMethod,
    KBDocument,
    RegionType,
)
from src.shared.models.artifact_models import (
    Artifact,
    ArtifactComponent,
    ArtifactComponentSource,
    ArtifactStatus,
    ArtifactType,
    ArtifactVersion,
    ComponentType,
)
from src.shared.models.audit_models import (
    AuditCheckpoint,
    AuditLog,
    NetworkEvent,
)

__all__ = [
    # Ops
    "User", "UserRole", "Session", "Message",
    "AgentTask", "TaskStatus", "AgentStep", "AgentStepStatus",
    "AgentEvent", "AgentCheckpoint", "Approval", "ApprovalDecision",
    "ModelRegistry", "RiskTier", "JobQueue",
    # KB
    "KBDocument", "AccessTagStatus", "DocumentExtraction", "RegionType", "ExtractionMethod",
    # Artifacts
    "Artifact", "ArtifactType", "ArtifactStatus", "ArtifactVersion",
    "ArtifactComponent", "ComponentType", "ArtifactComponentSource",
    # Audit
    "AuditLog", "AuditCheckpoint", "NetworkEvent",
]
