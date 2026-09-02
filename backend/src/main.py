"""
SENTINEL — Main FastAPI Application
Entry point that assembles all gateways, routers, and middleware.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.shared.config import get_settings
from src.shared.database import close_db, init_db

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sentinel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — startup and shutdown."""
    logger.info("=" * 60)
    logger.info("  SENTINEL — Self-Hosted Sovereign AI Workbench")
    logger.info(f"  Mode: {'SOVEREIGN' if settings.sovereign_mode else 'CONTROLLED'}")
    logger.info(f"  Environment: {settings.app_env}")
    logger.info("=" * 60)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Seed default admin user
    await _seed_default_users()

    yield

    # Shutdown
    await close_db()
    logger.info("SENTINEL shutdown complete")


app = FastAPI(
    title="SENTINEL — Sovereign AI Workbench",
    description=(
        "Self-hosted, sovereign-by-default AI workbench with multi-model routing, "
        "agentic execution through a mandatory policy gateway, multimodal document intelligence, "
        "permission-aware RAG, and a five-layer security architecture."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rate Limiting Middleware (FR8.1) ──────────────────────────
from collections import defaultdict
from time import time

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 100  # requests per minute


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting per IP (FR8.1)."""
    client_ip = request.client.host if request.client else "unknown"
    now = time()

    # Clean old entries
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < 60
    ]

    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )

    _rate_limit_store[client_ip].append(now)
    response = await call_next(request)
    return response


# ── Register Routers ─────────────────────────────────────────
from src.api_gateway.router import router as api_gateway_router
from src.model_gateway.api import router as model_gateway_router
from src.policy_gateway.gateway import router as policy_gateway_router
from src.sentinel_core.task_router import router as task_router
from src.sentinel_core.artifact_api import router as artifact_router
from src.knowledge_service.api import router as knowledge_router
from src.security.audit_log import router as security_router

app.include_router(api_gateway_router)
app.include_router(model_gateway_router)
app.include_router(policy_gateway_router)
app.include_router(task_router)
app.include_router(artifact_router)
app.include_router(knowledge_router)
app.include_router(security_router)


# ── Health / Status Endpoints ─────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "SENTINEL",
        "mode": "sovereign" if settings.sovereign_mode else "controlled",
    }


@app.get("/api/v1/dashboard")
async def get_dashboard(
    request: Request,
):
    """Dashboard overview data."""
    from src.policy_gateway.gateway import policy_gateway
    mode = policy_gateway.get_mode()

    return {
        "sovereignty_mode": mode.current_mode,
        "banner_text": mode.banner_text,
        "internet_status": mode.internet_status,
        "system_health": "healthy",
        "version": "1.0.0",
    }


# ── Seed Default Users ───────────────────────────────────────
async def _seed_default_users():
    """Create default admin and demo users."""
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from src.shared.database import async_session_factory
    from src.shared.models import User, UserRole
    from src.shared.auth import hash_password

    async with async_session_factory() as db:
        # Check if admin exists
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            users = [
                User(
                    username="admin",
                    email="admin@sentinel.local",
                    password_hash=hash_password("admin123"),
                    role=UserRole.ADMIN,
                    access_tags=["general", "engineering", "finance", "operations", "reports", "classified"],
                ),
                User(
                    username="engineer",
                    email="engineer@sentinel.local",
                    password_hash=hash_password("engineer123"),
                    role=UserRole.ENGINEER,
                    access_tags=["general", "engineering", "operations"],
                ),
                User(
                    username="analyst",
                    email="analyst@sentinel.local",
                    password_hash=hash_password("analyst123"),
                    role=UserRole.ANALYST,
                    access_tags=["general", "finance", "reports"],
                ),
                User(
                    username="viewer",
                    email="viewer@sentinel.local",
                    password_hash=hash_password("viewer123"),
                    role=UserRole.VIEWER,
                    access_tags=["general"],
                ),
            ]
            for user in users:
                db.add(user)
            try:
                await db.commit()
                logger.info("Default users seeded (admin, engineer, analyst, viewer)")
            except IntegrityError:
                await db.rollback()
                logger.info("Default users already exist (handled concurrent seed)")
