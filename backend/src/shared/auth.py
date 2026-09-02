"""
SENTINEL — Authentication & Authorization
JWT user tokens + service-identity tokens (FR7.4, FR8.1).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import get_settings
from src.shared.database import get_db
from src.shared.models.ops_models import User, UserRole

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# ── Password Hashing ─────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Token Creation ────────────────────────────────────────
def create_access_token(
    user_id: str,
    username: str,
    role: str,
    access_tags: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a user-facing JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "access_tags": access_tags or [],
        "type": "user",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_service_token(
    service_name: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a service-identity token (FR7.4) — distinct from user JWTs."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_service_token_expire_minutes)
    )
    payload = {
        "sub": service_name,
        "type": "service",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.service_token_secret, algorithm=settings.jwt_algorithm)


# ── JWT Token Verification ────────────────────────────────────
def decode_user_token(token: str) -> dict:
    """Decode and validate a user JWT."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "user":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
        )


def decode_service_token(token: str) -> dict:
    """Decode and validate a service-identity token."""
    try:
        payload = jwt.decode(token, settings.service_token_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "service":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid service token: {e}",
        )


# ── FastAPI Dependencies ──────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — extracts and validates the current user from JWT."""
    payload = decode_user_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency — requires admin role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def verify_service_identity(request: Request) -> dict:
    """Verify service-identity token from internal service calls (FR7.4)."""
    auth_header = request.headers.get("X-Service-Token")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service identity token required",
        )
    return decode_service_token(auth_header)
