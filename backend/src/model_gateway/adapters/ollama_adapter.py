"""
SENTINEL — Ollama adapter for local open-weight models (FR1.3).
Used for the air-gapped Sovereign Mode path. Never calls cloud APIs.
"""
from __future__ import annotations

import base64
import logging

import httpx

from src.model_gateway.adapters.base_adapter import BaseLLMAdapter
from src.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaAdapter(BaseLLMAdapter):
    provider = "ollama"

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            data = response.json()
            return (data.get("message") or {}).get("content") or ""

    async def vision_completion(
        self,
        model: str,
        prompt: str,
        image_data: bytes | str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        if isinstance(image_data, bytes):
            image_b64 = base64.b64encode(image_data).decode("utf-8")
        else:
            image_b64 = image_data
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            data = response.json()
            return (data.get("message") or {}).get("content") or ""

    async def generate_embedding(self, model: str, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            response.raise_for_status()
            return response.json().get("embedding") or []

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
