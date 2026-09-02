"""
SENTINEL — Planner
FR3.2: Task decomposition using LLM. Constructs capability-scoped execution contexts.
Handles replanning on verification failure.
"""
from __future__ import annotations

import json
import logging

from src.model_gateway.router import model_router
from src.model_gateway.execution_manager import execution_manager
from src.shared.schemas import CapabilityScopedContext

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the SENTINEL Planner. Your job is to decompose user goals into a sequence of concrete, executable steps.

Each step must specify:
- description: What this step does
- tool: Which tool to use (one of: fs_read, fs_write, code_exec, rag_search, rag_ingest, docx_create, xlsx_create, pptx_create, model_invoke, vision_analyze)
- risk_tier: LOW, MEDIUM, or HIGH
- dependencies: List of step indices this depends on

Available tools:
- fs_read: Read files from workspace
- fs_write: Write files to workspace
- code_exec: Execute code in sandboxed environment
- rag_search: Search knowledge base
- rag_ingest: Ingest documents into knowledge base
- docx_create: Create Word documents
- xlsx_create: Create Excel spreadsheets
- pptx_create: Create PowerPoint presentations
- model_invoke: Invoke LLM for reasoning/generation
- vision_analyze: Analyze images/documents with vision model

Output your plan as a JSON array of steps:
[
  {
    "step_order": 1,
    "description": "Search knowledge base for relevant documents",
    "tool": "rag_search",
    "risk_tier": "LOW",
    "dependencies": []
  },
  ...
]

IMPORTANT RULES:
1. Each step must use exactly ONE tool
2. Break complex tasks into atomic steps
3. Always include a verification step at the end
4. If creating documents, include a final model_invoke step for quality checking
5. Order steps by dependency — earlier steps first
6. Mark file finalization as HIGH risk (requires human approval)
"""


class Planner:
    """Task decomposition and plan construction (FR3.2)."""

    async def decompose(
        self,
        goal: str,
        user_role: str = "engineer",
        attachments: list[str] | None = None,
    ) -> dict:
        """
        Decompose a goal into executable steps using LLM.
        Returns the plan with steps and execution context.
        """
        # Route to reasoning model
        routing = model_router.route({
            "capabilities": ["planning", "tool_calling"],
            "vision": False,
            "tool_calling": True,
            "min_context": 4096,
        })

        if routing.status == "ROUTING_FAILURE":
            # Fallback to a simple default plan
            return self._default_plan(goal, attachments)

        # Ask LLM to decompose the task
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""Goal: {goal}
User role: {user_role}
Attachments: {json.dumps(attachments or [])}

Create an execution plan for this goal. Respond with ONLY the JSON array of steps."""},
        ]

        try:
            response = await execution_manager.invoke(
                model_id=routing.model_id,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )

            # Parse the plan from LLM response
            plan_steps = self._parse_plan(response)
            return {
                "goal": goal,
                "steps": plan_steps,
                "model_used": routing.model_id,
            }
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return self._default_plan(goal, attachments)

    def _parse_plan(self, response: str) -> list[dict]:
        """Parse plan steps from LLM response."""
        try:
            # Try to extract JSON from the response
            text = response.strip()
            # Find JSON array in response
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                steps = json.loads(json_str)
                if isinstance(steps, list):
                    return steps
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: create a single model_invoke step
        return [
            {
                "step_order": 1,
                "description": "Process the request using LLM",
                "tool": "model_invoke",
                "risk_tier": "LOW",
                "dependencies": [],
            }
        ]

    def _default_plan(self, goal: str, attachments: list[str] | None = None) -> dict:
        """Generate a default plan when LLM planning fails."""
        steps = []
        step_order = 1

        # If there are attachments, add a vision/OCR step
        if attachments:
            steps.append({
                "step_order": step_order,
                "description": "Analyze uploaded documents",
                "tool": "vision_analyze",
                "risk_tier": "LOW",
                "dependencies": [],
            })
            step_order += 1

        # Always search knowledge base
        steps.append({
            "step_order": step_order,
            "description": "Search knowledge base for relevant context",
            "tool": "rag_search",
            "risk_tier": "LOW",
            "dependencies": [],
        })
        step_order += 1

        # Main reasoning step
        steps.append({
            "step_order": step_order,
            "description": f"Generate response for: {goal[:200]}",
            "tool": "model_invoke",
            "risk_tier": "LOW",
            "dependencies": list(range(1, step_order)),
        })

        return {"goal": goal, "steps": steps, "model_used": "default"}

    async def replan(
        self,
        goal: str,
        failed_step: dict,
        error: list[str],
    ) -> dict:
        """Replan after a verification failure (FR3.7)."""
        routing = model_router.route({
            "capabilities": ["planning"],
            "vision": False,
            "min_context": 4096,
        })

        if routing.status == "ROUTING_FAILURE":
            return self._default_plan(goal)

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""The previous plan failed at this step:
Step: {json.dumps(failed_step)}
Errors: {json.dumps(error)}

Original goal: {goal}

Create a revised plan that addresses the errors. Respond with ONLY the JSON array of steps."""},
        ]

        try:
            response = await execution_manager.invoke(
                model_id=routing.model_id,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            plan_steps = self._parse_plan(response)
            return {"goal": goal, "steps": plan_steps, "model_used": routing.model_id, "replanned": True}
        except Exception as e:
            logger.error(f"Replanning failed: {e}")
            return self._default_plan(goal)


# Singleton
planner = Planner()
