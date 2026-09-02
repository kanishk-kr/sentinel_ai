"""
SENTINEL — Model Router (Decision-Only)
FR1.2: Matches task requirements against registered models.
Returns {model_id, reason[], confidence} or explicit ROUTING_FAILURE.
Never resolves endpoints — that's the Execution Manager's job.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import yaml

from src.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ModelManifestEntry:
    """A registered model's manifest entry."""
    id: str
    provider: str  # groq, gemini
    runtime_target: str  # API model name
    capabilities: list[str]
    context_window: int
    requirements: dict  # {vision: bool, tool_calling: bool}
    latency_class: str = "medium"
    approx_vram_gb: float | None = None
    active: bool = True


@dataclass
class RoutingResultData:
    """Result of a routing decision."""
    status: str  # "OK" or "ROUTING_FAILURE"
    model_id: str | None = None
    provider: str | None = None
    runtime_target: str | None = None
    reason: list[str] = field(default_factory=list)
    confidence: float = 0.0
    unmet_requirements: list[str] | None = None


class ModelRouter:
    """
    Decision-only Model Router (FR1.2).
    Matches task requirements against registered models.
    Never touches endpoints — the Execution Manager resolves runtime_target.
    """

    def __init__(self) -> None:
        self.models: dict[str, ModelManifestEntry] = {}
        self._load_default_models()

    def _load_default_models(self) -> None:
        """Load default model manifest for Groq + Gemini setup."""
        default_models = [
            ModelManifestEntry(
                id="reasoning-groq",
                provider="groq",
                runtime_target="qwen/qwen3.8-27b",
                capabilities=[
                    "general_qa", "planning", "summarization",
                    "tool_calling", "analysis", "writing",
                ],
                context_window=131072,
                requirements={"vision": False, "tool_calling": True},
                latency_class="fast",
            ),
            ModelManifestEntry(
                id="coding-groq",
                provider="groq",
                runtime_target="qwen/qwen3.8-27b",
                capabilities=[
                    "code", "code_review", "sandbox_debug",
                    "tool_calling", "planning",
                ],
                context_window=131072,
                requirements={"vision": False, "tool_calling": True},
                latency_class="fast",
            ),
            ModelManifestEntry(
                id="fast-groq",
                provider="groq",
                runtime_target="llama-3.1-8b-instant",
                capabilities=[
                    "general_qa", "summarization", "classification",
                ],
                context_window=131072,
                requirements={"vision": False, "tool_calling": False},
                latency_class="fast",
            ),
            ModelManifestEntry(
                id="vision-gemini",
                provider="gemini",
                runtime_target="gemini-2.0-flash",
                capabilities=[
                    "vision", "ocr_assist", "drawing_understanding",
                    "general_qa", "summarization", "analysis",
                    "planning", "tool_calling",
                ],
                context_window=1048576,
                requirements={"vision": True, "tool_calling": True},
                latency_class="medium",
            ),
            ModelManifestEntry(
                id="reasoning-gemini",
                provider="gemini",
                runtime_target="gemini-2.5-flash-preview-05-20",
                capabilities=[
                    "general_qa", "planning", "summarization",
                    "analysis", "writing", "tool_calling",
                    "code", "code_review",
                ],
                context_window=1048576,
                requirements={"vision": True, "tool_calling": True},
                latency_class="medium",
            ),
            ModelManifestEntry(
                id="embedding-gemini",
                provider="gemini",
                runtime_target="text-embedding-004",
                capabilities=["embedding"],
                context_window=2048,
                requirements={"vision": False, "tool_calling": False},
                latency_class="fast",
            ),
        ]
        for model in default_models:
            self.models[model.id] = model

    def register_model(self, entry: ModelManifestEntry) -> None:
        """Register a new model (FR1.5 — no core code changes needed)."""
        self.models[entry.id] = entry
        logger.info(f"Registered model: {entry.id} ({entry.provider})")

    def _satisfies(self, model: ModelManifestEntry, requirements: dict) -> tuple[bool, list[str]]:
        """Check if a model satisfies the given requirements."""
        unmet = []
        if requirements.get("vision") and not model.requirements.get("vision"):
            unmet.append("vision")
        if requirements.get("tool_calling") and not model.requirements.get("tool_calling"):
            unmet.append("tool_calling")
        if requirements.get("min_context", 0) > model.context_window:
            unmet.append(f"min_context ({requirements['min_context']} > {model.context_window})")

        # Check capability match
        required_capabilities = requirements.get("capabilities", [])
        for cap in required_capabilities:
            if cap not in model.capabilities:
                unmet.append(f"capability:{cap}")

        return len(unmet) == 0, unmet

    def _score(self, model: ModelManifestEntry, requirements: dict) -> float:
        """Score a model's fitness for the requirements."""
        score = 0.0
        required_capabilities = requirements.get("capabilities", [])
        if required_capabilities:
            matched = sum(1 for c in required_capabilities if c in model.capabilities)
            score += (matched / len(required_capabilities)) * 0.6
        else:
            score += 0.5

        # Prefer models with lower latency
        latency_scores = {"fast": 0.3, "medium": 0.2, "slow": 0.1}
        score += latency_scores.get(model.latency_class, 0.1)

        # Prefer larger context windows
        if model.context_window >= 100000:
            score += 0.1

        return min(score, 1.0)

    def route(self, requirements: dict) -> RoutingResultData:
        """
        Route a task to the best matching model (FR1.2).
        Decision-only — never resolves endpoints.
        Returns ROUTING_FAILURE with unmet requirements if no model matches.
        """
        candidates = []
        all_unmet = []

        for model in self.models.values():
            if not model.active:
                continue
            satisfies, unmet = self._satisfies(model, requirements)
            if satisfies:
                score = self._score(model, requirements)
                candidates.append((model, score))
            else:
                all_unmet.extend(unmet)

        if not candidates:
            unique_unmet = list(set(all_unmet)) if all_unmet else ["no active models registered"]
            logger.warning(f"ROUTING_FAILURE: No model satisfies {requirements}. Unmet: {unique_unmet}")
            return RoutingResultData(
                status="ROUTING_FAILURE",
                reason=[f"No registered model satisfies requirements: {requirements}"],
                unmet_requirements=unique_unmet,
            )

        # Sort by score, pick highest
        candidates.sort(key=lambda x: x[1], reverse=True)
        chosen, score = candidates[0]

        reasons = [
            f"Selected {chosen.id} ({chosen.provider})",
            f"Capabilities match: {[c for c in requirements.get('capabilities', []) if c in chosen.capabilities]}",
            f"Context window: {chosen.context_window}",
            f"Latency class: {chosen.latency_class}",
        ]

        return RoutingResultData(
            status="OK",
            model_id=chosen.id,
            provider=chosen.provider,
            runtime_target=chosen.runtime_target,
            reason=reasons,
            confidence=round(score, 3),
        )


# Singleton instance
model_router = ModelRouter()
