"""
SENTINEL — Groq LLM Adapter
Fast inference for Llama/Mixtral models via Groq API.
Used for reasoning and coding tasks.
"""
from __future__ import annotations

import logging

from groq import AsyncGroq

from src.model_gateway.adapters.base_adapter import BaseLLMAdapter
from src.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GroqAdapter(BaseLLMAdapter):
    """Groq API adapter for fast LLM inference."""

    provider = "groq"

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.groq_api_key)

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """Generate a chat completion via Groq."""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,  # Non-streaming for now
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Groq chat completion error: {e}")
            raise RuntimeError(f"Groq API error: {e}") from e

    async def vision_completion(
        self,
        model: str,
        prompt: str,
        image_data: bytes | str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Groq has limited vision support — delegates to Gemini for vision tasks."""
        # Groq's Llama models with vision support
        try:
            if isinstance(image_data, bytes):
                import base64
                image_data = base64.b64encode(image_data).decode("utf-8")

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        },
                    ],
                }
            ]
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Groq vision error: {e}")
            raise RuntimeError(f"Groq vision not supported for this model: {e}") from e

    async def generate_embedding(
        self,
        model: str,
        text: str,
    ) -> list[float]:
        """Groq does not support embeddings — raise error to fallback."""
        raise NotImplementedError("Groq does not support embeddings. Use Gemini or local model.")

    async def health_check(self) -> bool:
        """Check Groq API availability."""
        try:
            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(response.choices)
        except Exception:
            return False
