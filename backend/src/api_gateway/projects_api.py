"""
SENTINEL — Projects API
Manage user projects with working directories for code execution context.
"""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth import get_current_user
from src.shared.database import get_db
from src.shared.models import Project, Session, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Projects"])


# ── Schemas ───────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    working_dir: str = Field(..., min_length=1)  # Host path selected by user


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    working_dir: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    working_dir: str
    created_at: str
    updated_at: str
    session_count: int = 0

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class FileNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int | None = None
    children: list["FileNode"] | None = None


# ── CRUD Endpoints ────────────────────────────────────────────
@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project with a working directory."""
    project = Project(
        user_id=user.id,
        name=request.name,
        description=request.description,
        working_dir=request.working_dir,
    )
    db.add(project)
    await db.flush()

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        working_dir=project.working_dir,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        session_count=0,
    )


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all projects for the current user."""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user.id)
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()

    project_responses = []
    for p in projects:
        # Count sessions in this project
        session_count_result = await db.execute(
            select(Session).where(Session.project_id == p.id)
        )
        session_count = len(session_count_result.scalars().all())

        project_responses.append(ProjectResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            working_dir=p.working_dir,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
            session_count=session_count,
        ))

    return ProjectListResponse(projects=project_responses, total=len(project_responses))


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single project by ID."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == user.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    session_count_result = await db.execute(
        select(Session).where(Session.project_id == project.id)
    )
    session_count = len(session_count_result.scalars().all())

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        working_dir=project.working_dir,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        session_count=session_count,
    )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == user.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description
    if request.working_dir is not None:
        project.working_dir = request.working_dir

    await db.flush()

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        working_dir=project.working_dir,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        session_count=0,
    )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project and orphan its sessions."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == user.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Orphan sessions (set project_id to NULL)
    sessions_result = await db.execute(
        select(Session).where(Session.project_id == project.id)
    )
    for session in sessions_result.scalars().all():
        session.project_id = None
    await db.flush()

    await db.delete(project)
    await db.flush()

    return {"status": "deleted", "id": project_id}


# ── File Explorer Endpoint ────────────────────────────────────
@router.get("/projects/{project_id}/files")
async def list_project_files(
    project_id: str,
    path: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List files in a project's working directory."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == user.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    base_dir = project.working_dir
    target_dir = os.path.join(base_dir, path) if path else base_dir

    # Security: ensure we don't escape the working directory
    target_dir = os.path.realpath(target_dir)
    if not target_dir.startswith(os.path.realpath(base_dir)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal denied")

    if not os.path.isdir(target_dir):
        return {"files": [], "working_dir": base_dir, "error": "Directory not found"}

    files = []
    try:
        for entry in sorted(os.scandir(target_dir), key=lambda e: (not e.is_dir(), e.name.lower())):
            # Skip hidden files and common noise
            if entry.name.startswith(".") or entry.name in ("node_modules", "__pycache__", ".git"):
                continue
            files.append({
                "name": entry.name,
                "path": os.path.relpath(entry.path, base_dir),
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else None,
            })
    except PermissionError:
        return {"files": [], "working_dir": base_dir, "error": "Permission denied"}

    return {"files": files, "working_dir": base_dir}


@router.get("/projects/{project_id}/files/content")
async def get_file_content(
    project_id: str,
    path: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read file content from a project's working directory."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == user.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    file_path = os.path.join(project.working_dir, path)
    file_path = os.path.realpath(file_path)

    # Security: path traversal prevention
    if not file_path.startswith(os.path.realpath(project.working_dir)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal denied")

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    try:
        with open(file_path, "r", errors="replace") as f:
            content = f.read(100_000)  # Limit to 100KB
        return {
            "path": path,
            "content": content,
            "size": os.path.getsize(file_path),
            "truncated": os.path.getsize(file_path) > 100_000,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot read file: {e}")
