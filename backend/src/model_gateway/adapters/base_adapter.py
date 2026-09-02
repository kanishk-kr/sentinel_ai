"""
SENTINEL — LLM Adapter Base Class
Abstract interface for all LLM providers. The Model Execution Manager
is the sole caller of these adapters (FR1.3).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    provider: str = "base"

    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """Generate a chat completion."""
        ...

    @abstractmethod
    async def vision_completion(
        self,
        model: str,
        prompt: str,
        image_data: bytes | str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a vision-based completion (image + text)."""
        ...

    @abstractmethod
    async def generate_embedding(
        self,
        model: str,
        text: str,
    ) -> list[float]:
        """Generate an embedding vector for text."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable."""
        ...
