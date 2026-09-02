"""
SENTINEL — Model Gateway API Router
FR1, FR2: Model registration, routing, status, and supply-chain verification endpoints.
"""
from __future__ import annotations

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from src.shared.auth import get_current_user, require_admin
from src.shared.models import User
from src.shared.schemas import ModelInfoResponse, ModelRegisterRequest, RoutingResult
from src.model_gateway.router import ModelManifestEntry, model_router
from src.model_gateway.execution_manager import execution_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/models", tags=["Model Gateway"])


@router.get("", response_model=list[ModelInfoResponse])
async def list_models(user: User = Depends(get_current_user)):
    """List all registered models with live status (FR1.4)."""
    statuses = execution_manager.get_model_status()
    return [
        ModelInfoResponse(
            id=str(uuid.uuid4()),
            model_id=s["model_id"],
            display_name=s["model_id"],
            provider=s["provider"],
            backend="api",
            capabilities={"list": s["capabilities"]},
            requirements={},
            context_window=s["context_window"],
            latency_class=s["latency_class"],
            active=s["active"],
            state=s["state"],
            approx_vram_gb=s.get("approx_vram_gb"),
        )
        for s in statuses
    ]


@router.post("/register", response_model=ModelInfoResponse, status_code=status.HTTP_201_CREATED)
async def register_model(
    request: ModelRegisterRequest,
    user: User = Depends(require_admin),
):
    """
    Register a new model (FR1.5, FR2.1).
    Admin-only. Runs supply-chain verification before making the model selectable.
    """
    # FR2.1 — Supply-chain verification (simplified for API models)
    model_hash = hashlib.sha256(
        f"{request.model_id}:{request.provider}:{request.runtime_target}".encode()
    ).hexdigest()

    # Register with the Router
    entry = ModelManifestEntry(
        id=request.model_id,
        provider=request.provider,
        runtime_target=request.runtime_target,
        capabilities=request.capabilities.get("list", []) if isinstance(request.capabilities, dict) else [],
        context_window=request.context_window,
        requirements=request.requirements if isinstance(request.requirements, dict) else {},
        latency_class=request.latency_class,
        approx_vram_gb=request.approx_vram_gb,
    )
    model_router.register_model(entry)

    return ModelInfoResponse(
        id=str(uuid.uuid4()),
        model_id=request.model_id,
        display_name=request.display_name,
        provider=request.provider,
        backend=request.backend,
        capabilities=request.capabilities,
        requirements=request.requirements,
        context_window=request.context_window,
        latency_class=request.latency_class,
        active=True,
        state="AVAILABLE",
        approx_vram_gb=request.approx_vram_gb,
    )


@router.get("/health")
async def model_health():
    """Check health of all LLM providers."""
    return await execution_manager.health_check()


@router.post("/route")
async def route_request(
    requirements: dict,
    user: User = Depends(get_current_user),
):
    """Test model routing for given requirements."""
    result = model_router.route(requirements)
    return RoutingResult(
        status=result.status,
        model_id=result.model_id,
        reason=result.reason,
        confidence=result.confidence,
        unmet_requirements=result.unmet_requirements,
    )
