"""
SENTINEL — API Gateway Router
FR8.1: Single frontend entry point. Auth, session handling, rate limiting,
WebSocket routing, /api/v1 (public) vs /internal/v1 (service-only) boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from src.shared.database import get_db
from src.shared.models import (
    Message,
    Session,
    User,
    UserRole,
)
from src.shared.schemas import (
    LoginRequest,
    LoginResponse,
    MessageCreate,
    MessageResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/api/v1", tags=["API Gateway"])


# ══════════════════════════════════════════════════════════════
# Auth Endpoints
# ══════════════════════════════════════════════════════════════
@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT (FR8.1)."""
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role.value,
        access_tags=user.access_tags or [],
    )
    return LoginResponse(
        access_token=token,
        user_id=str(user.id),
        username=user.username,
        role=user.role.value,
    )


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user (admin-only in production, open for demo)."""
    existing = await db.execute(select(User).where(User.username == request.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        role=UserRole(request.role) if request.role in [r.value for r in UserRole] else UserRole.VIEWER,
        access_tags=["general"],  # Default access tag
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ══════════════════════════════════════════════════════════════
# Session Endpoints (FR9.3 — chat history management)
# ══════════════════════════════════════════════════════════════
@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    session = Session(user_id=user.id, title=request.title)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return SessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all sessions for the current user (FR9.3)."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
    )
    sessions = result.scalars().all()

    session_list = []
    for s in sessions:
        msg_count_result = await db.execute(
            select(func.count(Message.id)).where(Message.session_id == s.id)
        )
        msg_count = msg_count_result.scalar() or 0
        session_list.append(
            SessionResponse(
                id=str(s.id),
                user_id=str(s.user_id),
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=msg_count,
            )
        )
    return SessionListResponse(sessions=session_list, total=len(session_list))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific session."""
    result = await db.execute(
        select(Session).where(Session.id == uuid.UUID(session_id), Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msg_count_result = await db.execute(
        select(func.count(Message.id)).where(Message.session_id == session.id)
    )
    msg_count = msg_count_result.scalar() or 0
    return SessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=msg_count,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a session and all its messages."""
    result = await db.execute(
        select(Session).where(Session.id == uuid.UUID(session_id), Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.delete(session)


# ══════════════════════════════════════════════════════════════
# Message Endpoints (FR9.3, FR9.4)
# ══════════════════════════════════════════════════════════════
@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all messages for a session."""
    # Verify session ownership
    sess_result = await db.execute(
        select(Session).where(Session.id == uuid.UUID(session_id), Session.user_id == user.id)
    )
    if not sess_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = await db.execute(
        select(Message)
        .where(Message.session_id == uuid.UUID(session_id))
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        MessageResponse(
            id=str(m.id),
            session_id=str(m.session_id),
            role=m.role,
            content=m.content,
            model_used=m.model_used,
            evidence_confidence_json=m.evidence_confidence_json,
            citations=m.citations,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def create_message(
    session_id: str,
    request: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a response (synchronous/streamed chat — FR9.3).
    This calls the Model Gateway via the Policy Gateway for inference.
    """
    # Verify session ownership
    sess_result = await db.execute(
        select(Session).where(Session.id == uuid.UUID(session_id), Session.user_id == user.id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Save user message
    user_msg = Message(
        session_id=uuid.UUID(session_id),
        role="user",
        content=request.content,
    )
    db.add(user_msg)
    await db.flush()

    # Get chat history for context
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == uuid.UUID(session_id))
        .order_by(Message.created_at.asc())
    )
    history = history_result.scalars().all()

    # Route through Model Gateway for inference
    from src.model_gateway.router import model_router
    from src.model_gateway.execution_manager import execution_manager

    # Determine requirements
    requirements = {"vision": False, "tool_calling": False, "min_context": 4096}

    # Route to best model
    routing = model_router.route(requirements)
    if routing.status == "ROUTING_FAILURE":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No model available: {routing.reason}",
        )

    # Build messages for LLM
    llm_messages = [
        {"role": "system", "content": (
            "You are SENTINEL, a sovereign AI workbench assistant. "
            "You help users with document analysis, code generation, data processing, and knowledge retrieval. "
            "Always provide accurate, well-cited responses. "
            "When referencing documents, cite specific pages and sections."
        )}
    ]
    for msg in history:
        llm_messages.append({"role": msg.role, "content": msg.content})

    # Invoke model
    try:
        response_text = await execution_manager.invoke(
            model_id=routing.model_id,
            messages=llm_messages,
        )
    except Exception as e:
        response_text = f"I encountered an error processing your request: {str(e)}"

    # Save assistant message
    assistant_msg = Message(
        session_id=uuid.UUID(session_id),
        role="assistant",
        content=response_text,
        model_used=routing.model_id,
    )
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    # Update session title if first message
    if len(history) <= 1:
        session.title = request.content[:100]

    return MessageResponse(
        id=str(assistant_msg.id),
        session_id=str(assistant_msg.session_id),
        role=assistant_msg.role,
        content=assistant_msg.content,
        model_used=assistant_msg.model_used,
        evidence_confidence_json=assistant_msg.evidence_confidence_json,
        citations=assistant_msg.citations,
        created_at=assistant_msg.created_at,
    )
