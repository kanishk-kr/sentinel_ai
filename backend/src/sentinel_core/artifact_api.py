"""
SENTINEL — Artifact Manager API
FR6.1-6.4: Versioned artifacts with component-level provenance.
Draft → Validate → Preview → Human Approval → Final lifecycle.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth import get_current_user, require_admin
from src.shared.database import get_db
from src.shared.models import (
    Approval,
    ApprovalDecision,
    Artifact,
    ArtifactComponent,
    ArtifactComponentSource,
    ArtifactStatus,
    ArtifactVersion,
    RiskTier,
    User,
)
from src.shared.schemas import (
    ArtifactApproveRequest,
    ArtifactResponse,
    ArtifactVersionResponse,
    ProvenanceResponse,
    SourceResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/artifacts", tags=["Artifact Manager"])


@router.get("", response_model=list[ArtifactResponse])
async def list_artifacts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all artifacts."""
    result = await db.execute(
        select(Artifact).order_by(Artifact.created_at.desc()).limit(50)
    )
    artifacts = result.scalars().all()

    response = []
    for art in artifacts:
        versions_result = await db.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == art.id)
            .order_by(ArtifactVersion.version_number.asc())
        )
        versions = versions_result.scalars().all()

        response.append(ArtifactResponse(
            id=str(art.id),
            task_id=str(art.task_id),
            artifact_type=art.artifact_type.value,
            title=art.title,
            current_version=art.current_version,
            status=art.status.value,
            versions=[
                ArtifactVersionResponse(
                    id=str(v.id),
                    version_number=v.version_number,
                    storage_path=v.storage_path,
                    generating_model=v.generating_model,
                    verification_verdict=v.verification_verdict_json,
                    created_at=v.created_at,
                )
                for v in versions
            ],
            created_at=art.created_at,
        ))
    return response


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get artifact with component-level provenance (FR6.1)."""
    result = await db.execute(
        select(Artifact).where(Artifact.id == uuid.UUID(artifact_id))
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    # Get versions
    versions_result = await db.execute(
        select(ArtifactVersion)
        .where(ArtifactVersion.artifact_id == art.id)
        .order_by(ArtifactVersion.version_number.asc())
    )
    versions = versions_result.scalars().all()

    # Get component-level provenance for latest version
    provenance = []
    if versions:
        latest_version = versions[-1]
        components_result = await db.execute(
            select(ArtifactComponent)
            .where(ArtifactComponent.artifact_version_id == latest_version.id)
        )
        components = components_result.scalars().all()

        for comp in components:
            sources_result = await db.execute(
                select(ArtifactComponentSource)
                .where(ArtifactComponentSource.artifact_component_id == comp.id)
            )
            sources = sources_result.scalars().all()

            provenance.append(ProvenanceResponse(
                component_type=comp.component_type.value,
                locator=comp.locator,
                content_preview=comp.content_preview,
                sources=[
                    SourceResponse(
                        source_document_title=s.source_document_title,
                        page_number=s.page_number,
                        bbox=s.bbox_json,
                        confidence=s.confidence,
                    )
                    for s in sources
                ],
            ))

    return ArtifactResponse(
        id=str(art.id),
        task_id=str(art.task_id),
        artifact_type=art.artifact_type.value,
        title=art.title,
        current_version=art.current_version,
        status=art.status.value,
        versions=[
            ArtifactVersionResponse(
                id=str(v.id),
                version_number=v.version_number,
                storage_path=v.storage_path,
                generating_model=v.generating_model,
                verification_verdict=v.verification_verdict_json,
                created_at=v.created_at,
            )
            for v in versions
        ],
        provenance=provenance,
        created_at=art.created_at,
    )


@router.post("/{artifact_id}/approve")
async def approve_artifact(
    artifact_id: str,
    request: ArtifactApproveRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Human approval → finalize artifact version (FR6.4).
    HIGH-risk action requiring admin approval.
    """
    result = await db.execute(
        select(Artifact).where(Artifact.id == uuid.UUID(artifact_id))
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    if art.status == ArtifactStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Artifact already approved")

    art.status = ArtifactStatus.APPROVED

    # Create approval record
    approval = Approval(
        artifact_id=art.id,
        requested_by=user.id,
        approver_id=user.id,
        decision=ApprovalDecision.APPROVED,
        risk_tier=RiskTier.HIGH,
        action_description=f"Approved artifact: {art.title}",
        comment=request.comment,
    )
    db.add(approval)
    await db.flush()

    # Audit log
    from src.security.audit_log import audit_service
    import hashlib
    await audit_service.log(
        db=db,
        entry_type="approval_decision",
        actor=str(user.id),
        action="artifact_approved",
        resource=str(art.id),
        input_hash=hashlib.sha256(str(art.id).encode()).hexdigest(),
        allowed=True,
        risk_tier="HIGH",
    )

    return {"id": str(art.id), "status": "approved", "approved_by": user.username}


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    version: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download an artifact file."""
    result = await db.execute(
        select(Artifact).where(Artifact.id == uuid.UUID(artifact_id))
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    # Get the requested version
    if version:
        ver_result = await db.execute(
            select(ArtifactVersion).where(
                ArtifactVersion.artifact_id == art.id,
                ArtifactVersion.version_number == version,
            )
        )
    else:
        ver_result = await db.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == art.id)
            .order_by(ArtifactVersion.version_number.desc())
            .limit(1)
        )
    ver = ver_result.scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    from pathlib import Path
    filepath = Path(ver.storage_path)
    if not filepath.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="application/octet-stream",
    )
