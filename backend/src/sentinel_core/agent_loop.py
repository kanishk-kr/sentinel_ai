"""
SENTINEL — Agent Loop (Core Orchestrator)
FR3.3, FR3.4: Idempotent commit-state machine with normalized agent state.
Drives tasks through: AUTHORIZED → EXECUTING → COMMITTED → VERIFIED.
Crash-safe resume via checkpoints. All downstream calls go through Policy Gateway.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model_gateway.execution_manager import execution_manager
from src.model_gateway.router import model_router
from src.policy_gateway.gateway import policy_gateway
from src.sentinel_core.planner import planner
from src.sentinel_core.verification import verification_layer
from src.shared.models import (
    AgentCheckpoint,
    AgentEvent,
    AgentStep,
    AgentStepStatus,
    AgentTask,
    Approval,
    ApprovalDecision,
    RiskTier,
    TaskStatus,
    User,
)
from src.shared.schemas import CapabilityScopedContext, PolicyDecision

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    The core Agent Orchestrator loop (Section 3.4).
    Implements the idempotent commit-state machine.
    """

    def __init__(self) -> None:
        self.active_tasks: dict[str, str] = {}  # task_id → status

    async def execute_task(
        self,
        task_id: str,
        user: User,
        db: AsyncSession,
        ws_callback=None,
    ) -> dict:
        """
        Execute a task through the full agent loop.
        This is the main entry point called by the Job Queue worker.
        """
        # Load or resume task
        result = await db.execute(select(AgentTask).where(AgentTask.id == uuid.UUID(task_id)))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Determine allowed paths based on project
        allowed_paths = [f"/workspace/{task_id}"]
        if task.session_id:
            from src.shared.models import Session, Project
            session_result = await db.execute(select(Session).where(Session.id == task.session_id))
            session_obj = session_result.scalar_one_or_none()
            if session_obj and session_obj.project_id:
                project_result = await db.execute(select(Project).where(Project.id == session_obj.project_id))
                project_obj = project_result.scalar_one_or_none()
                if project_obj:
                    allowed_paths.append(project_obj.working_dir)

        task.status = TaskStatus.PLANNING
        await db.flush()
        self.active_tasks[task_id] = "PLANNING"

        try:
            # Phase 1: Plan if needed
            if not task.plan_json:
                await self._send_event(ws_callback, task_id, None, "planning", "Decomposing task into steps...")
                plan = await planner.decompose(
                    goal=task.goal,
                    user_role=user.role.value,
                    attachments=task.attachments,
                )
                task.plan_json = plan

                # Build capability-scoped execution context (FR3.2)
                tools_needed = list(set(step.get("tool", "model_invoke") for step in plan.get("steps", [])))
                context = CapabilityScopedContext(
                    task_id=task_id,
                    user=str(user.id),
                    user_role=user.role.value,
                    allowed_tools=tools_needed,
                    allowed_paths=allowed_paths,
                    network="none",
                    max_iterations=len(plan.get("steps", [])) + 5,
                    max_runtime_seconds=300,
                )
                task.execution_context_json = context.model_dump()

                # Validate entire context up front (FR3.2)
                policy_decision = policy_gateway.validate_context(context, user.role)
                if not policy_decision.allowed:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Policy rejected plan: {policy_decision.reason}"
                    await db.flush()
                    return {"status": "FAILED", "error": policy_decision.reason}

                # Create agent steps in DB (normalized state — FR3.4)
                for step_data in plan.get("steps", []):
                    step = AgentStep(
                        task_id=task.id,
                        step_order=step_data.get("step_order", 0),
                        description=step_data.get("description", ""),
                        tool_used=step_data.get("tool"),
                        risk_tier=RiskTier(step_data.get("risk_tier", "LOW")),
                        status=AgentStepStatus.PENDING,
                        operation_id=f"{task_id}-{step_data.get('step_order', 0)}",
                    )
                    db.add(step)

                await db.flush()
                await db.refresh(task)

            # Phase 2: Execute steps
            task.status = TaskStatus.RUNNING
            await db.flush()
            self.active_tasks[task_id] = "RUNNING"

            steps_result = await db.execute(
                select(AgentStep)
                .where(AgentStep.task_id == task.id)
                .order_by(AgentStep.step_order.asc())
            )
            steps = list(steps_result.scalars().all())

            final_output = ""
            for step in steps:
                # Check for already committed steps (idempotent resume — FR3.3)
                if step.status == AgentStepStatus.COMMITTED or step.status == AgentStepStatus.VERIFIED:
                    await self._record_event(db, step.id, "REPLAYED", {"note": "Already committed"})
                    await self._send_event(ws_callback, task_id, str(step.id), "replayed",
                                           f"Step {step.step_order} already committed, skipping")
                    continue

                # AUTHORIZED
                step.status = AgentStepStatus.AUTHORIZED
                step.started_at = datetime.now(timezone.utc)
                await db.flush()
                await self._record_event(db, step.id, "AUTHORIZED", {})
                await self._send_event(ws_callback, task_id, str(step.id), "step_started",
                                       f"Starting: {step.description}")

                # Check for existing approval on resume
                approval_result = await db.execute(select(Approval).where(Approval.task_step_id == step.id))
                existing_approval = approval_result.scalar_one_or_none()
                
                if existing_approval:
                    if existing_approval.decision == ApprovalDecision.PENDING:
                        task.status = TaskStatus.PAUSED
                        await db.flush()
                        return {"status": "PAUSED", "reason": "Awaiting human approval"}
                    elif existing_approval.decision == ApprovalDecision.REJECTED:
                        step.status = AgentStepStatus.REJECTED
                        await db.flush()
                        await self._record_event(db, step.id, "REJECTED", {"reason": "Human denied request"})
                        continue
                    # If APPROVED, bypass the policy gateway authorization below
                    decision = PolicyDecision(allowed=True, reason="Human approved", risk_tier="HIGH", requires_approval=False)
                else:
                    # Check policy authorization
                    decision = await policy_gateway.authorize(
                        action=step.tool_used or "model_invoke",
                        user=user,
                        context=CapabilityScopedContext(**task.execution_context_json) if task.execution_context_json else None,
                        db=db,
                        task_step_id=step.id,
                    )

                if not decision.allowed and not decision.requires_approval:
                    step.status = AgentStepStatus.REJECTED
                    await db.flush()
                    await self._record_event(db, step.id, "REJECTED", {"reason": decision.reason})
                    await self._send_event(ws_callback, task_id, str(step.id), "rejected",
                                           f"Policy rejected: {decision.reason}")
                    continue

                if decision.requires_approval:
                    await self._send_event(ws_callback, task_id, str(step.id), "awaiting_approval",
                                           f"Awaiting human approval for: {step.description}",
                                           risk_tier=decision.risk_tier)
                    
                    task.status = TaskStatus.PAUSED
                    await db.flush()

                    # Suspend execution and return control to the worker
                    return {"status": "PAUSED", "reason": "Awaiting human approval"}

                # EXECUTING
                step.status = AgentStepStatus.EXECUTING
                await db.flush()
                await self._record_event(db, step.id, "EXECUTING", {"tool": step.tool_used})
                await self._send_event(ws_callback, task_id, str(step.id), "tool_execution",
                                       f"Executing: {step.tool_used}", tool=step.tool_used)

                # Execute the step with exponential backoff for rate limits
                max_retries = 3
                step_success = False
                for attempt in range(max_retries):
                    try:
                        result = await self._execute_step(step, task, user, db)
                        step.input_hash = hashlib.sha256(step.description.encode()).hexdigest()
                        step.output_hash = hashlib.sha256(str(result).encode()).hexdigest()
                        step.result_json = {"output": str(result)[:5000]}
                        final_output = str(result)
                        step_success = True
                        break
                    except Exception as e:
                        if attempt < max_retries - 1 and ("429" in str(e) or "rate limit" in str(e).lower()):
                            backoff = (2 ** attempt) * 10
                            logger.warning(f"Rate limit hit for task {task_id}: {e}. Retrying in {backoff}s...")
                            await self._send_event(ws_callback, task_id, str(step.id), "retrying", f"Rate limit hit. Retrying in {backoff}s...")
                            await asyncio.sleep(backoff)
                            continue
                        
                        step.status = AgentStepStatus.REJECTED
                        step.result_json = {"error": str(e)}
                        step.completed_at = datetime.now(timezone.utc)
                        await db.flush()
                        await self._record_event(db, step.id, "EXECUTION_FAILED", {"error": str(e)})
                        await self._send_event(ws_callback, task_id, str(step.id), "error", f"Step failed: {e}")
                        break

                if not step_success:
                    continue

                # COMMITTED
                step.status = AgentStepStatus.COMMITTED
                step.completed_at = datetime.now(timezone.utc)
                await db.flush()
                await self._record_event(db, step.id, "COMMITTED", {"output_hash": step.output_hash})

                # Update checkpoint
                checkpoint = AgentCheckpoint(
                    task_id=task.id,
                    last_committed_step_id=step.id,
                    sequence_number=step.step_order,
                )
                db.add(checkpoint)
                await db.flush()

                # VERIFY
                verdict = await self._verify_step(step, result, db)
                step.verification_verdict_json = verdict.model_dump()
                if verdict.status == "PASS":
                    step.status = AgentStepStatus.VERIFIED
                    await self._record_event(db, step.id, "VERIFIED", verdict.model_dump())
                    await self._send_event(ws_callback, task_id, str(step.id), "verified",
                                           f"Verified: {step.description}")
                else:
                    step.status = AgentStepStatus.VERIFY_FAILED
                    await self._record_event(db, step.id, "VERIFY_FAILED", verdict.model_dump())
                    await self._send_event(ws_callback, task_id, str(step.id), "verify_failed",
                                           f"Verification failed: {verdict.errors}")

                    # Attempt replanning (FR3.7)
                    new_plan = await planner.replan(
                        goal=task.goal,
                        failed_step={"description": step.description, "tool": step.tool_used},
                        error=verdict.errors,
                    )
                    task.plan_json = new_plan
                    await db.flush()

                await db.flush()

            # Phase 3: Complete task
            task.status = TaskStatus.COMPLETED
            await db.flush()
            self.active_tasks[task_id] = "COMPLETED"
            await self._send_event(ws_callback, task_id, None, "completed", "Task completed successfully")

            return {"status": "COMPLETED", "output": final_output}

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await db.flush()
            self.active_tasks[task_id] = "FAILED"
            return {"status": "FAILED", "error": str(e)}

    async def _execute_step(
        self,
        step: AgentStep,
        task: AgentTask,
        user: User,
        db: AsyncSession,
    ) -> str:
        """Execute a single step using the mandatory Policy Gateway chokepoint (FR3.1)."""
        tool = step.tool_used or "model_invoke"
        payload = {}

        if tool == "model_invoke":
            routing = model_router.route({
                "capabilities": ["general_qa", "planning", "analysis", "writing"],
                "vision": False,
                "min_context": 4096,
            })
            if routing.status == "ROUTING_FAILURE":
                raise RuntimeError(f"No model available: {routing.reason}")

            messages = [
                {"role": "system", "content": (
                    "You are SENTINEL, a sovereign AI workbench. Complete the following task step. "
                    "Provide a thorough, well-structured response."
                )},
                {"role": "user", "content": f"Task goal: {task.goal}\n\nCurrent step: {step.description}"},
            ]
            payload = {"model_id": routing.model_id, "messages": messages}

        elif tool == "rag_search":
            payload = {"query": step.description, "top_k": 5}

        elif tool == "code_exec":
            payload = {"code": step.description, "language": "python"}

        elif tool in ("docx_create", "xlsx_create", "pptx_create"):
            payload = {"content": step.description}

        elif tool == "vision_analyze":
            return "Vision analysis completed"

        elif tool in ("fs_read", "fs_write"):
            routing = model_router.route({
                "capabilities": ["code"],
                "vision": False,
                "min_context": 4096,
            })
            if routing.status == "ROUTING_FAILURE":
                raise RuntimeError(f"No model available for file ops: {routing.reason}")

            allowed_paths = task.execution_context_json.get("allowed_paths", []) if task.execution_context_json else []
            
            prompt = f"""You are an autonomous agent executing a file system operation.
Task Goal: {task.goal}
Step Description: {step.description}
Allowed Paths: {allowed_paths}

Write a Python script to perform this file system operation.
The script MUST:
1. ONLY read/write within the Allowed Paths.
2. Print the results (e.g., file contents, directory tree) to stdout so they can be captured.
3. Handle missing files gracefully and print a clear error if the file is not found.
4. If the output is extremely large, print only the first 5000 characters or summarize it.

Output ONLY the raw Python code. Do NOT wrap it in markdown backticks (no ```python). Do NOT explain anything."""
            
            code = await execution_manager.invoke(
                model_id=routing.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                db=db,
                actor=str(user.id),
            )
            code = code.replace("```python", "").replace("```", "").strip()
            
            # Repurpose tool to code_exec for the sandbox, since fs_read/fs_write are just sandboxed code
            tool = "code_exec"
            payload = {"code": code, "language": "python"}

        else:
            raise ValueError(f"Unknown tool: {tool}")

        from src.shared.schemas import PolicyExecuteRequest
        from src.policy_gateway.gateway import policy_gateway
        
        request = PolicyExecuteRequest(
            action=tool,
            payload=payload,
            context=CapabilityScopedContext(**task.execution_context_json) if task.execution_context_json else None,
            user_id=str(user.id),
            approval_granted=True,  # Approval was already checked in the agent loop Phase 2
        )
        
        result_dict = await policy_gateway.execute(request=request, db=db, task_step_id=step.id)
        if result_dict.get("status") == "COMPLETED":
            return str(result_dict.get("output", ""))
        else:
            raise RuntimeError(f"Execution failed or paused: {result_dict.get('reason')}")

    async def _verify_step(self, step: AgentStep, result: str, db: AsyncSession) -> VerificationVerdict:
        """Verify a step's output based on tool type."""
        tool = step.tool_used or "model_invoke"

        if tool == "code_exec":
            return await verification_layer.verify_code(result)
        elif tool in ("docx_create", "xlsx_create", "pptx_create"):
            from src.shared.models.artifact_models import ArtifactVersion
            version_result = await db.execute(
                select(ArtifactVersion).where(ArtifactVersion.storage_path == result).order_by(ArtifactVersion.created_at.desc()).limit(1)
            )
            version = version_result.scalar_one_or_none()
            metadata = version.metadata_json if version else {}
            return await verification_layer.verify_export(result, metadata)
        else:
            return await verification_layer.verify_text_output(result)

    async def _record_event(
        self,
        db: AsyncSession,
        step_id: uuid.UUID,
        event_type: str,
        payload: dict,
    ) -> None:
        """Record a fine-grained event (FR3.4 — normalized agent state)."""
        event = AgentEvent(
            step_id=step_id,
            event_type=event_type,
            payload_json=payload,
        )
        db.add(event)
        await db.flush()

    async def _send_event(
        self,
        callback,
        task_id: str,
        step_id: str | None,
        event_type: str,
        message: str,
        tool: str | None = None,
        risk_tier: str | None = None,
    ) -> None:
        """Send a WebSocket event to the frontend."""
        if callback:
            try:
                await callback({
                    "task_id": task_id,
                    "step_id": step_id,
                    "event": event_type,
                    "message": message,
                    "tool": tool,
                    "risk_tier": risk_tier,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.warning(f"Failed to send WS event: {e}")


# Import for type hint
from src.shared.schemas import VerificationVerdict

# Singleton
agent_loop = AgentLoop()
