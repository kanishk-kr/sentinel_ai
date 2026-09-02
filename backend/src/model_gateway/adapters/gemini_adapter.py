"""
SENTINEL — Google Gemini LLM Adapter
Vision + reasoning + embeddings via Gemini API.
"""
from __future__ import annotations

import base64
import logging

from google import genai
from google.genai import types

from src.model_gateway.adapters.base_adapter import BaseLLMAdapter
from src.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GeminiAdapter(BaseLLMAdapter):
    """Google Gemini API adapter for vision, reasoning, and embeddings."""

    provider = "gemini"

    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """Generate a chat completion via Gemini."""
        try:
            # Convert OpenAI-format messages to Gemini format
            contents = []
            system_instruction = None

            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg["content"])],
                    ))
                elif msg["role"] == "assistant":
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=msg["content"])],
                    ))

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            if system_instruction:
                config.system_instruction = system_instruction

            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"Gemini chat completion error: {e}")
            raise RuntimeError(f"Gemini API error: {e}") from e

    async def vision_completion(
        self,
        model: str,
        prompt: str,
        image_data: bytes | str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a vision-based completion with Gemini (FR4.1 — region-level vision)."""
        try:
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data

            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png",
            )
            text_part = types.Part.from_text(text=prompt)

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            response = self.client.models.generate_content(
                model=model,
                contents=[types.Content(
                    role="user",
                    parts=[text_part, image_part],
                )],
                config=config,
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"Gemini vision error: {e}")
            raise RuntimeError(f"Gemini vision API error: {e}") from e

    async def generate_embedding(
        self,
        model: str,
        text: str,
    ) -> list[float]:
        """Generate text embedding via Gemini."""
        try:
            response = self.client.models.embed_content(
                model=model,
                contents=text,
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            raise RuntimeError(f"Gemini embedding API error: {e}") from e

    async def health_check(self) -> bool:
        """Check Gemini API availability."""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=5),
            )
            return bool(response.text)
        except Exception:
            return False
