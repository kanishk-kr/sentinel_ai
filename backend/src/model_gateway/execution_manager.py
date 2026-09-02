"""
SENTINEL — Model Execution Manager
FR1.3: Execution-only. The sole component that talks to LLM providers.
Resolves model_id → provider + runtime_target → actual API call.
Owns model lifecycle, adapted for API-based models (connection pooling, rate limiting).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.model_gateway.adapters import get_adapter
from src.model_gateway.router import model_router

logger = logging.getLogger(__name__)


class ModelExecutionManager:
    """
    Model Execution Manager (FR1.3).
    The ONLY component that resolves model_id → runtime_target → actual API call.
    For API-based models: manages connection pooling and request tracking.
    For local models (future): manages VRAM budget, load/unload, lifecycle states.
    """

    def __init__(self) -> None:
        self.model_states: dict[str, dict] = {}  # model_id → state info
        self.request_count: dict[str, int] = {}  # model_id → request count
        self.last_used: dict[str, datetime] = {}  # model_id → last used timestamp

    def _get_model_info(self, model_id: str) -> dict:
        """Resolve model_id to provider and runtime_target."""
        model = model_router.models.get(model_id)
        if not model:
            raise ValueError(f"Model '{model_id}' not found in registry")
        return {
            "provider": model.provider,
            "runtime_target": model.runtime_target,
            "capabilities": model.capabilities,
            "context_window": model.context_window,
        }

    async def invoke(
        self,
        model_id: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Invoke a model for chat completion.
        The sole entry point for all LLM inference in SENTINEL.
        """
        info = self._get_model_info(model_id)
        adapter = get_adapter(info["provider"])

        logger.info(f"Invoking model {model_id} ({info['provider']}:{info['runtime_target']})")

        result = await adapter.chat_completion(
            model=info["runtime_target"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Track usage
        self.request_count[model_id] = self.request_count.get(model_id, 0) + 1
        self.last_used[model_id] = datetime.now(timezone.utc)
        self.model_states[model_id] = {
            "state": "AVAILABLE",
            "last_used": self.last_used[model_id].isoformat(),
            "request_count": self.request_count[model_id],
        }

        return result

    async def invoke_vision(
        self,
        model_id: str,
        prompt: str,
        image_data: bytes | str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Invoke a vision model (FR4.1 — region-level vision)."""
        info = self._get_model_info(model_id)
        adapter = get_adapter(info["provider"])

        logger.info(f"Invoking vision model {model_id}")

        result = await adapter.vision_completion(
            model=info["runtime_target"],
            prompt=prompt,
            image_data=image_data,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        self.request_count[model_id] = self.request_count.get(model_id, 0) + 1
        self.last_used[model_id] = datetime.now(timezone.utc)
        return result

    async def generate_embedding(
        self,
        text: str,
        model_id: str = "embedding-gemini",
    ) -> list[float]:
        """Generate an embedding vector for text."""
        info = self._get_model_info(model_id)
        adapter = get_adapter(info["provider"])

        return await adapter.generate_embedding(
            model=info["runtime_target"],
            text=text,
        )

    def get_model_status(self) -> list[dict]:
        """Get live status of all registered models (FR1.4 — Model Resource Dashboard)."""
        statuses = []
        for model_id, model in model_router.models.items():
            state_info = self.model_states.get(model_id, {})
            statuses.append({
                "model_id": model_id,
                "provider": model.provider,
                "runtime_target": model.runtime_target,
                "state": state_info.get("state", "AVAILABLE"),
                "capabilities": model.capabilities,
                "context_window": model.context_window,
                "latency_class": model.latency_class,
                "active": model.active,
                "request_count": self.request_count.get(model_id, 0),
                "last_used": self.last_used.get(model_id, None),
                "approx_vram_gb": model.approx_vram_gb,
            })
        return statuses

    async def health_check(self) -> dict[str, bool]:
        """Check health of all LLM providers."""
        results = {}
        checked_providers = set()
        for model_id, model in model_router.models.items():
            if model.provider not in checked_providers:
                try:
                    adapter = get_adapter(model.provider)
                    results[model.provider] = await adapter.health_check()
                except Exception:
                    results[model.provider] = False
                checked_providers.add(model.provider)
        return results


# Singleton instance
execution_manager = ModelExecutionManager()
