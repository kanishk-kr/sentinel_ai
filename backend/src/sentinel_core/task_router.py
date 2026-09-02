"""
SENTINEL — Task Router & Job Queue
FR3.5: POST /tasks enqueues a job; Worker process picks it up.
FR9.5: WebSocket streaming for task progress.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.sentinel_core.agent_loop import agent_loop
from src.shared.auth import get_current_user
from src.shared.database import async_session_factory, get_db
from src.shared.models import (
    AgentStep,
    AgentTask,
    JobQueue,
    TaskStatus,
    User,
)
from src.shared.schemas import TaskCreate, TaskDetailResponse, TaskResponse, StepResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])

# WebSocket connections per task
ws_connections: dict[str, list[WebSocket]] = {}


@router.post("", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    request: TaskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enqueue an agent task (FR3.5).
    Returns 202 Accepted + task_id immediately. Task is processed asynchronously.
    """
    # Create agent task
    task = AgentTask(
        user_id=user.id,
        session_id=uuid.UUID(request.session_id) if request.session_id else None,
        goal=request.goal,
        status=TaskStatus.QUEUED,
        attachments=request.attachments,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Enqueue in job queue (Postgres-based — Section 2.2)
    job = JobQueue(task_id=task.id, status="pending")
    db.add(job)
    await db.flush()

    # Start async processing (in production, a separate worker process picks this up)
    asyncio.create_task(_process_task(str(task.id), str(user.id)))

    return TaskResponse(task_id=str(task.id), status="accepted")


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get task status + Agent State summary (FR9.5)."""
    result = await db.execute(
        select(AgentTask).where(AgentTask.id == uuid.UUID(task_id), AgentTask.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Get steps
    steps_result = await db.execute(
        select(AgentStep)
        .where(AgentStep.task_id == task.id)
        .order_by(AgentStep.step_order.asc())
    )
    steps = steps_result.scalars().all()

    return TaskDetailResponse(
        id=str(task.id),
        goal=task.goal,
        status=task.status.value,
        plan=task.plan_json,
        execution_context=task.execution_context_json,
        steps=[
            StepResponse(
                id=str(s.id),
                step_order=s.step_order,
                description=s.description,
                tool_used=s.tool_used,
                model_used=s.model_used,
                risk_tier=s.risk_tier.value,
                status=s.status.value,
                operation_id=s.operation_id,
                verification_verdict=s.verification_verdict_json,
                started_at=s.started_at,
                completed_at=s.completed_at,
            )
            for s in steps
        ],
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("", response_model=list[TaskDetailResponse])
async def list_tasks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tasks for current user."""
    result = await db.execute(
        select(AgentTask)
        .where(AgentTask.user_id == user.id)
        .order_by(AgentTask.created_at.desc())
        .limit(50)
    )
    tasks = result.scalars().all()

    response = []
    for task in tasks:
        steps_result = await db.execute(
            select(AgentStep)
            .where(AgentStep.task_id == task.id)
            .order_by(AgentStep.step_order.asc())
        )
        steps = steps_result.scalars().all()

        response.append(TaskDetailResponse(
            id=str(task.id),
            goal=task.goal,
            status=task.status.value,
            plan=task.plan_json,
            execution_context=task.execution_context_json,
            steps=[
                StepResponse(
                    id=str(s.id),
                    step_order=s.step_order,
                    description=s.description,
                    tool_used=s.tool_used,
                    model_used=s.model_used,
                    risk_tier=s.risk_tier.value,
                    status=s.status.value,
                    operation_id=s.operation_id,
                    verification_verdict=s.verification_verdict_json,
                    started_at=s.started_at,
                    completed_at=s.completed_at,
                )
                for s in steps
            ],
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
        ))
    return response


@router.websocket("/{task_id}/stream")
async def task_stream(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task progress (FR9.5)."""
    await websocket.accept()

    if task_id not in ws_connections:
        ws_connections[task_id] = []
    ws_connections[task_id].append(websocket)

    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if task_id in ws_connections:
            ws_connections[task_id].remove(websocket)
            if not ws_connections[task_id]:
                del ws_connections[task_id]


async def _broadcast_event(task_id: str, event: dict) -> None:
    """Broadcast an event to all WebSocket connections for a task."""
    if task_id in ws_connections:
        disconnected = []
        for ws in ws_connections[task_id]:
            try:
                await ws.send_json(event)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            ws_connections[task_id].remove(ws)


async def _process_task(task_id: str, user_id: str) -> None:
    """
    Background task processor.
    In production, this runs as a separate Worker process consuming from the job queue.
    Uses SELECT ... FOR UPDATE SKIP LOCKED (FR3.5).
    """
    async with async_session_factory() as db:
        try:
            # Load user
            user_result = await db.execute(
                select(User).where(User.id == uuid.UUID(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                logger.error(f"User {user_id} not found for task {task_id}")
                return

            # Lock the job (SELECT FOR UPDATE SKIP LOCKED)
            job_result = await db.execute(
                select(JobQueue)
                .where(JobQueue.task_id == uuid.UUID(task_id), JobQueue.status == "pending")
                .with_for_update(skip_locked=True)
            )
            job = job_result.scalar_one_or_none()
            if not job:
                logger.info(f"Job for task {task_id} already picked up by another worker")
                return

            job.status = "processing"
            job.locked_at = datetime.now(timezone.utc)
            await db.flush()

            # Execute the agent loop
            async def ws_callback(event: dict) -> None:
                await _broadcast_event(task_id, event)

            result = await agent_loop.execute_task(
                task_id=task_id,
                user=user,
                db=db,
                ws_callback=ws_callback,
            )

            # Update job status
            job.status = "completed" if result.get("status") == "COMPLETED" else "failed"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            logger.error(f"Task processing failed: {e}", exc_info=True)
            await db.rollback()
            # Update job status to failed
            async with async_session_factory() as db2:
                await db2.execute(
                    update(JobQueue)
                    .where(JobQueue.task_id == uuid.UUID(task_id))
                    .values(status="failed", completed_at=datetime.now(timezone.utc))
                )
                await db2.commit()
