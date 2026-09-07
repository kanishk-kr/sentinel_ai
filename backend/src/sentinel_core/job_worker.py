"""
SENTINEL — Job Queue worker (FR3.5).
Consumes Postgres jobs with SELECT ... FOR UPDATE SKIP LOCKED.
Survives backend restart: pending/processing jobs are re-picked.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from src.shared.database import async_session_factory
from src.shared.models import AgentStep, AgentTask, JobQueue, Message, User

logger = logging.getLogger(__name__)
WORKER_ID = os.environ.get("HOSTNAME", "orchestrator-worker")


async def claim_next_job(db) -> JobQueue | None:
    result = await db.execute(
        select(JobQueue)
        .where(JobQueue.status == "pending")
        .order_by(JobQueue.priority.desc(), JobQueue.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return None
    job.status = "processing"
    job.locked_by = WORKER_ID
    job.locked_at = datetime.now(timezone.utc)
    await db.flush()
    return job


async def process_claimed_job(job: JobQueue, db) -> None:
    from src.sentinel_core.agent_loop import agent_loop
    from src.sentinel_core.task_router import _broadcast_event

    task_result = await db.execute(select(AgentTask).where(AgentTask.id == job.task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        return

    user_result = await db.execute(select(User).where(User.id == task.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        return

    async def ws_callback(event: dict) -> None:
        await _broadcast_event(str(task.id), event)

    result = await agent_loop.execute_task(
        task_id=str(task.id),
        user=user,
        db=db,
        ws_callback=ws_callback,
    )

    if result.get("status") == "PAUSED":
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        return

    job.status = "completed" if result.get("status") == "COMPLETED" else "failed"
    job.completed_at = datetime.now(timezone.utc)

    if task.session_id:
        if job.status == "completed":
            steps_result = await db.execute(
                select(AgentStep)
                .where(AgentStep.task_id == task.id)
                .order_by(AgentStep.step_order.desc())
                .limit(1)
            )
            last_step = steps_result.scalar_one_or_none()
            final_output = "Task completed successfully, but no output was recorded."
            if last_step and last_step.result_json:
                if isinstance(last_step.result_json, dict) and "output" in last_step.result_json:
                    final_output = last_step.result_json["output"]
                elif isinstance(last_step.result_json, str):
                    final_output = last_step.result_json
                else:
                    final_output = json.dumps(last_step.result_json, indent=2)
            db.add(Message(
                session_id=task.session_id,
                role="assistant",
                content=f"🎉 **Task Completed** (ID: {task.id})\n\n**Result:**\n\n{final_output}",
            ))
        else:
            db.add(Message(
                session_id=task.session_id,
                role="assistant",
                content=f"❌ **Task Failed** (ID: {task.id})\n\n{result.get('error', 'Unknown error')}",
            ))


async def job_worker_loop(stop_event: asyncio.Event) -> None:
    logger.info("Job queue worker started (SKIP LOCKED)")
    while not stop_event.is_set():
        try:
            async with async_session_factory() as db:
                job = await claim_next_job(db)
                if not job:
                    await db.rollback()
                else:
                    try:
                        await process_claimed_job(job, db)
                        await db.commit()
                    except Exception:
                        logger.exception("Job %s failed", job.id)
                        await db.rollback()
                        async with async_session_factory() as db2:
                            await db2.execute(
                                update(JobQueue)
                                .where(JobQueue.id == job.id)
                                .values(status="failed", completed_at=datetime.now(timezone.utc))
                            )
                            await db2.commit()
                        continue
        except Exception:
            logger.exception("Job worker loop error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            continue


_stop_event: asyncio.Event | None = None
_worker_task: asyncio.Task | None = None


async def start_job_worker() -> None:
    global _stop_event, _worker_task
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(job_worker_loop(_stop_event))


async def stop_job_worker() -> None:
    global _stop_event, _worker_task
    if _stop_event:
        _stop_event.set()
    if _worker_task:
        await _worker_task
        _worker_task = None
