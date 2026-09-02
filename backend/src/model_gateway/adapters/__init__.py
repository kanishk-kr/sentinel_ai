"""
SENTINEL — Adapter Registry
Maps provider names to their adapter implementations.
"""
from src.model_gateway.adapters.base_adapter import BaseLLMAdapter
from src.model_gateway.adapters.groq_adapter import GroqAdapter
from src.model_gateway.adapters.gemini_adapter import GeminiAdapter

__all__ = ["BaseLLMAdapter", "GroqAdapter", "GeminiAdapter", "get_adapter"]

_adapters: dict[str, BaseLLMAdapter] = {}


def get_adapter(provider: str) -> BaseLLMAdapter:
    """Get or create a cached adapter instance for the given provider."""
    if provider not in _adapters:
        if provider == "groq":
            _adapters[provider] = GroqAdapter()
        elif provider == "gemini":
            _adapters[provider] = GeminiAdapter()
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    return _adapters[provider]
