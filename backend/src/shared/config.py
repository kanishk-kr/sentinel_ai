"""
SENTINEL — Application Configuration
Centralized settings loaded from environment variables with validation.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ───────────────────────────────────────────────
    app_name: str = "SENTINEL"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # ── Backend ───────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_workers: int = 1
    cors_origins: str = "http://localhost:3000"

    # ── Database ──────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "sentinel"
    postgres_user: str = "sentinel_app"
    postgres_password: str = "change_me_in_production"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Vector Database ───────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "kb_chunks"

    # ── Redis ─────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379

    # ── JWT / Auth ────────────────────────────────────────────
    jwt_secret_key: str = "change_this_to_a_strong_random_secret_key_at_least_32_chars"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_service_token_expire_minutes: int = 15

    # ── LLM Providers ────────────────────────────────────────
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # ── Model Configuration ──────────────────────────────────
    default_reasoning_model: str = "groq:qwen/qwen3.8-27b"
    default_coding_model: str = "groq:qwen/qwen3.8-27b"
    default_vision_model: str = "gemini:gemini-2.0-flash"
    default_embedding_model: str = "gemini:text-embedding-004"

    # ── File Storage ──────────────────────────────────────────
    upload_dir: str = "./uploads"
    artifact_store_dir: str = "./artifacts_store"
    sandbox_dir: str = "./sandbox"
    max_upload_size_mb: int = 50

    # ── Security ──────────────────────────────────────────────
    sovereign_mode: bool = True
    service_token_secret: str = "change_this_service_token_secret"
    model_signing_public_key_path: str = "./secrets/model_signing_pub.pem"

    # ── Audit ─────────────────────────────────────────────────
    audit_checkpoint_interval: int = 100

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def artifact_store_path(self) -> Path:
        p = Path(self.artifact_store_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def sandbox_path(self) -> Path:
        p = Path(self.sandbox_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
