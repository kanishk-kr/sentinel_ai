"""
SENTINEL — Application Configuration
Secrets are loaded from Docker secret files when present (FR7.8).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret_file(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "SENTINEL"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    service_role: str = "monolith"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_workers: int = 1
    cors_origins: str = "http://localhost:3000"

    postgres_host: str = Field(default="localhost", validation_alias=AliasChoices("POSTGRES_HOST", "DB_HOST"))
    postgres_port: int = Field(default=5432, validation_alias=AliasChoices("POSTGRES_PORT", "DB_PORT"))
    postgres_db: str = Field(default="sentinel", validation_alias=AliasChoices("POSTGRES_DB", "DB_NAME"))
    postgres_user: str = Field(default="sentinel_app", validation_alias=AliasChoices("POSTGRES_USER", "DB_USER"))
    postgres_password: str = Field(
        default="change_me_in_production",
        validation_alias=AliasChoices("POSTGRES_PASSWORD", "DB_PASS"),
    )
    postgres_password_file: str | None = None
    postgres_owner_user: str = "sentinel_owner"
    postgres_owner_password: str = ""
    postgres_owner_password_file: str | None = None

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "kb_chunks"

    redis_host: str = "localhost"
    redis_port: int = 6379

    jwt_secret_key: str = "change_this_to_a_strong_random_secret_key_at_least_32_chars"
    jwt_secret_key_file: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_service_token_expire_minutes: int = 15

    groq_api_key: str = ""
    groq_api_key_file: str | None = None
    gemini_api_key: str = ""
    gemini_api_key_file: str | None = None

    ollama_base_url: str = "http://ollama-runtime:11434"
    ollama_reasoning_model: str = "qwen2.5:7b"
    ollama_coding_model: str = "qwen2.5-coder:7b"
    ollama_vision_model: str = "llava:7b"
    ollama_embed_model: str = "nomic-embed-text"

    upload_dir: str = "./uploads"
    artifact_store_dir: str = "./artifacts_store"
    sandbox_dir: str = "./sandbox"
    max_upload_size_mb: int = 50

    sovereign_mode: bool = True
    allow_cloud_llms: bool = True
    service_token_secret: str = "change_this_service_token_secret"
    service_token_secret_file: str | None = None
    model_signing_public_key_path: str = "./secrets/model_signing_pub.pem"
    require_service_token: bool = True

    policy_gateway_url: str = ""
    model_gateway_url: str = ""
    knowledge_gateway_url: str = ""
    sandbox_worker_url: str = ""

    audit_checkpoint_interval: int = 100

    @model_validator(mode="after")
    def load_docker_secrets(self) -> "Settings":
        mapping = [
            ("postgres_password", self.postgres_password_file, "/run/secrets/postgres_password"),
            ("postgres_owner_password", self.postgres_owner_password_file, "/run/secrets/postgres_owner_password"),
            ("jwt_secret_key", self.jwt_secret_key_file, "/run/secrets/jwt_secret"),
            ("service_token_secret", self.service_token_secret_file, "/run/secrets/service_token_secret"),
            ("groq_api_key", self.groq_api_key_file, "/run/secrets/groq_api_key"),
            ("gemini_api_key", self.gemini_api_key_file, "/run/secrets/gemini_api_key"),
        ]
        for field_name, explicit_file, docker_path in mapping:
            value = _read_secret_file(explicit_file) or _read_secret_file(docker_path)
            if value:
                setattr(self, field_name, value)
        if not self.postgres_owner_password:
            self.postgres_owner_password = self.postgres_password
        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_owner_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_owner_user}:{self.postgres_owner_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

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
    return Settings()
