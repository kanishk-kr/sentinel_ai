"""
SENTINEL — Policy Gateway (Mandatory Chokepoint)
FR3.1, FR3.2, FR3.8, FR7.1-7.4: The ONLY service with network routes to
Model/Tool/Knowledge Gateways. Authenticates, authorizes, risk-classifies,
and forwards requests. NEVER re-derives permissions from untrusted content.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth import get_current_user, require_admin, verify_service_identity
from src.shared.config import get_settings
from src.shared.database import get_db
from src.shared.models import (
    Approval,
    ApprovalDecision,
    RiskTier,
    User,
    UserRole,
)
from src.shared.schemas import (
    ApprovalDecisionRequest,
    ApprovalResponse,
    CapabilityScopedContext,
    PolicyDecision,
    SecurityModeChangeRequest,
    SecurityModeResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Policy Gateway"])

# ── RBAC Permission Matrix ────────────────────────────────────
ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        "allowed_tools": [
            "fs_read", "fs_write", "code_exec", "rag_search", "rag_ingest",
            "docx_create", "xlsx_create", "pptx_create", "model_invoke",
            "vision_analyze", "admin_classify", "mode_toggle",
        ],
        "max_risk_tier": RiskTier.HIGH,
        "can_approve": True,
        "access_tags": ["*"],  # All tags
    },
    UserRole.ENGINEER: {
        "allowed_tools": [
            "fs_read", "fs_write", "code_exec", "rag_search",
            "docx_create", "xlsx_create", "pptx_create", "model_invoke",
            "vision_analyze",
        ],
        "max_risk_tier": RiskTier.MEDIUM,
        "can_approve": False,
        "access_tags": ["general", "engineering", "operations"],
    },
    UserRole.ANALYST: {
        "allowed_tools": [
            "fs_read", "rag_search", "docx_create", "xlsx_create",
            "pptx_create", "model_invoke", "vision_analyze",
        ],
        "max_risk_tier": RiskTier.LOW,
        "can_approve": False,
        "access_tags": ["general", "finance", "reports"],
    },
    UserRole.VIEWER: {
        "allowed_tools": ["fs_read", "rag_search", "model_invoke"],
        "max_risk_tier": RiskTier.LOW,
        "can_approve": False,
        "access_tags": ["general"],
    },
}


# ── Risk Classification ──────────────────────────────────────
TOOL_RISK_MAP = {
    "fs_read": RiskTier.LOW,
    "rag_search": RiskTier.LOW,
    "model_invoke": RiskTier.LOW,
    "vision_analyze": RiskTier.LOW,
    "fs_write": RiskTier.MEDIUM,
    "docx_create": RiskTier.MEDIUM,
    "xlsx_create": RiskTier.MEDIUM,
    "pptx_create": RiskTier.MEDIUM,
    "code_exec": RiskTier.MEDIUM,
    "admin_classify": RiskTier.MEDIUM,
    "artifact_finalize": RiskTier.HIGH,
    "controlled_egress": RiskTier.HIGH,
    "mode_toggle": RiskTier.HIGH,
    "rag_ingest": RiskTier.MEDIUM,
}


class PolicyGateway:
    """
    The mandatory policy chokepoint (FR3.1).
    All requests from the Agent Orchestrator pass through here.
    """

    def __init__(self) -> None:
        self.sovereign_mode = settings.sovereign_mode
        self._mode_last_changed: datetime | None = None

    def classify_risk(self, action: str) -> RiskTier:
        """Classify risk tier for an action."""
        return TOOL_RISK_MAP.get(action, RiskTier.MEDIUM)

    def validate_context(
        self,
        context: CapabilityScopedContext,
        user_role: UserRole,
    ) -> PolicyDecision:
        """
        Validate the ENTIRE capability-scoped execution context up front (FR3.2).
        Not just per-step — the whole plan must be authorized.
        """
        perms = ROLE_PERMISSIONS.get(user_role, ROLE_PERMISSIONS[UserRole.VIEWER])

        # Check each allowed tool against role permissions
        for tool in context.allowed_tools:
            if tool not in perms["allowed_tools"]:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Tool '{tool}' not permitted for role '{user_role.value}'",
                    risk_tier="HIGH",
                )

        # Check network access
        if context.network == "controlled" and self.sovereign_mode:
            return PolicyDecision(
                allowed=False,
                reason="Controlled network access not available in Sovereign Mode",
                risk_tier="HIGH",
            )

        return PolicyDecision(allowed=True, reason="Context validated", risk_tier="LOW")

    async def authorize(
        self,
        action: str,
        user: User,
        context: CapabilityScopedContext | None = None,
        db: AsyncSession | None = None,
    ) -> PolicyDecision:
        """
        Authorize an action against RBAC + risk tiers + execution context (FR3.1).
        FR3.8 INVARIANT: Never re-derives permissions from untrusted content.
        Permissions come ONLY from the pre-validated execution context.
        """
        perms = ROLE_PERMISSIONS.get(user.role, ROLE_PERMISSIONS[UserRole.VIEWER])
        risk_tier = self.classify_risk(action)

        # Check if action is in allowed tools
        if action not in perms["allowed_tools"]:
            logger.warning(f"Action '{action}' denied for user '{user.username}' (role: {user.role})")
            return PolicyDecision(
                allowed=False,
                reason=f"Action '{action}' not permitted for role '{user.role.value}'",
                risk_tier=risk_tier.value,
            )

        # Check context constraints if provided
        if context and action not in context.allowed_tools:
            return PolicyDecision(
                allowed=False,
                reason=f"Action '{action}' not in task execution context",
                risk_tier=risk_tier.value,
            )

        # Check if risk tier requires approval
        requires_approval = False
        approval_id = None
        if risk_tier == RiskTier.HIGH:
            requires_approval = True
            if db:
                approval = Approval(
                    requested_by=user.id,
                    decision=ApprovalDecision.PENDING,
                    risk_tier=risk_tier,
                    action_description=f"Action: {action}",
                )
                db.add(approval)
                await db.flush()
                approval_id = str(approval.id)

        return PolicyDecision(
            allowed=True if not requires_approval else False,
            reason="Authorized" if not requires_approval else "Awaiting human approval",
            risk_tier=risk_tier.value,
            requires_approval=requires_approval,
            approval_id=approval_id,
        )

    def get_mode(self) -> SecurityModeResponse:
        """Get current security mode (FR7.1, FR7.2)."""
        if self.sovereign_mode:
            return SecurityModeResponse(
                current_mode="sovereign",
                sovereign_mode=True,
                internet_status="blocked",
                banner_text="SOVEREIGN MODE — Internet: Blocked",
                last_changed=self._mode_last_changed,
            )
        else:
            return SecurityModeResponse(
                current_mode="controlled",
                sovereign_mode=False,
                internet_status="restricted",
                banner_text="CONTROLLED MODE — Internet: Restricted",
                last_changed=self._mode_last_changed,
            )

    def set_mode(self, mode: str) -> SecurityModeResponse:
        """Toggle security mode (admin-only, separately authenticated — FR7.2)."""
        self.sovereign_mode = mode == "sovereign"
        self._mode_last_changed = datetime.now(timezone.utc)
        logger.info(f"Security mode changed to: {mode}")
        return self.get_mode()


# Singleton
policy_gateway = PolicyGateway()


# ══════════════════════════════════════════════════════════════
# API Routes
# ══════════════════════════════════════════════════════════════

# ── Public endpoints ──────────────────────────────────────────
@router.get("/api/v1/security/mode", response_model=SecurityModeResponse)
async def get_security_mode(user: User = Depends(get_current_user)):
    """Get current security mode (FR7.1)."""
    return policy_gateway.get_mode()


@router.post("/api/v1/security/mode", response_model=SecurityModeResponse)
async def set_security_mode(
    request: SecurityModeChangeRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle security mode (admin-only — FR7.2)."""
    from src.security.audit_log import audit_service
    result = policy_gateway.set_mode(request.mode)
    await audit_service.log(
        db=db,
        entry_type="mode_change",
        actor=str(user.id),
        action=f"mode_changed_to_{request.mode}",
        input_hash=hashlib.sha256(request.mode.encode()).hexdigest(),
        allowed=True,
        risk_tier="HIGH",
    )
    return result


# ── Approval endpoints (FR3.6) ───────────────────────────────
@router.get("/api/v1/policy/pending-approvals", response_model=list[ApprovalResponse])
async def get_pending_approvals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pending approvals (admin sees all, others see their own)."""
    if user.role == UserRole.ADMIN:
        result = await db.execute(
            select(Approval)
            .where(Approval.decision == ApprovalDecision.PENDING)
            .order_by(Approval.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Approval)
            .where(
                Approval.decision == ApprovalDecision.PENDING,
                Approval.requested_by == user.id,
            )
            .order_by(Approval.created_at.desc())
        )
    approvals = result.scalars().all()
    return [
        ApprovalResponse(
            id=str(a.id),
            task_step_id=str(a.task_step_id) if a.task_step_id else None,
            artifact_id=str(a.artifact_id) if a.artifact_id else None,
            requested_by=str(a.requested_by),
            approver_id=str(a.approver_id) if a.approver_id else None,
            decision=a.decision.value,
            risk_tier=a.risk_tier.value,
            action_description=a.action_description,
            comment=a.comment,
            decided_at=a.decided_at,
            created_at=a.created_at,
        )
        for a in approvals
    ]


@router.post("/api/v1/policy/approvals/{approval_id}", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a pending approval (admin-only — FR3.6)."""
    result = await db.execute(
        select(Approval).where(Approval.id == uuid.UUID(approval_id))
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    if approval.decision != ApprovalDecision.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already decided")

    approval.decision = ApprovalDecision(request.decision)
    approval.approver_id = user.id
    approval.comment = request.comment
    approval.decided_at = datetime.now(timezone.utc)
    await db.flush()

    return ApprovalResponse(
        id=str(approval.id),
        task_step_id=str(approval.task_step_id) if approval.task_step_id else None,
        artifact_id=str(approval.artifact_id) if approval.artifact_id else None,
        requested_by=str(approval.requested_by),
        approver_id=str(approval.approver_id),
        decision=approval.decision.value,
        risk_tier=approval.risk_tier.value,
        action_description=approval.action_description,
        comment=approval.comment,
        decided_at=approval.decided_at,
        created_at=approval.created_at,
    )
