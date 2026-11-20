"""Application configuration using Pydantic Settings with dev/prod environment support"""

import json
import os
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator


def _resolve_env_file() -> str:
    """Resolve environment file based on ENV_FILE or APP_ENV/ENVIRONMENT variables."""
    explicit_file = os.getenv("ENV_FILE")
    if explicit_file:
        return explicit_file
    app_env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "")).lower().strip()
    for prefix in ("", "backend/"):
        if app_env in ("production", "prod") and os.path.exists(f"{prefix}.env.prod"):
            return f"{prefix}.env.prod"
        if app_env in ("development", "dev") and os.path.exists(f"{prefix}.env.dev"):
            return f"{prefix}.env.dev"
        if os.path.exists(f"{prefix}.env"):
            return f"{prefix}.env"
    return ".env"


class Settings(BaseSettings):
    """Application settings with multi-environment variable support"""

    # Application
    APP_NAME: str = "WVISMIS - WinVinaya MIS"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, production, testing
    FRONTEND_URL: Optional[str] = None

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Database (PostgreSQL - wvismis)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "wvismis"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[str] = None

    @model_validator(mode="after")
    def assemble_db_connection(self) -> "Settings":
        """Construct async PostgreSQL database URL from components if not explicitly set"""
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Security & JWT
    SECRET_KEY: str = "wvismis_default_secret_key_change_in_production_32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Default Bootstrap Admin & Organization
    FIRST_SUPERUSER: str = "dharanidaran.a@winvinaya.com"
    FIRST_SUPERUSER_PASSWORD: str = "Testpass@123"
    DEFAULT_ORGANIZATION_NAME: str = "WinVinaya Infosystems"
    DEFAULT_ORGANIZATION_SLUG: str = "winvinaya"

    # CORS
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://localhost:3000"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str], None]) -> List[str]:
        """Parse CORS origins from comma-separated string, JSON string, or list"""
        if v is None or v == "":
            return ["*"]
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("["):
                try:
                    return json.loads(v_str)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 2000

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_ROTATION: str = "500 MB"
    LOG_RETENTION: str = "30 days"
    LOG_FORMAT: str = "json"  # json or text

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # WebSockets & Real-Time Streaming
    WS_HEARTBEAT_INTERVAL_SECONDS: int = 30
    WS_MAX_CONNECTIONS_PER_ORG: int = 500

    # ── Harness Agentic AI Engine ────────────────────────────────────────────
    AI_ENABLED: bool = True
    AI_PROVIDER: str = "anthropic"  # anthropic | gemini | openai | mistral | ollama
    AI_FALLBACK_PROVIDER: str = "gemini"  # secondary fallback provider

    # Provider API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    TOGETHER_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None

    # Default Models Per Provider
    AI_MODEL_ANTHROPIC: str = "claude-3-7-sonnet-20250219"
    AI_MODEL_GEMINI: str = "gemini-3.6-flash,gemini-3.5-flash-lite"
    AI_MODEL_OPENAI: str = "gpt-4o-mini"
    AI_MODEL_MISTRAL: str = "mistral-small-latest"
    AI_MODEL_TOGETHER: str = "meta-llama/Llama-3.1-8B-Instruct-Turbo"
    AI_MODEL_COHERE: str = "command-r"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # Harness Safety & Guardrails
    AI_MAX_TOOL_CALLS_PER_RUN: int = 15
    AI_TASK_TIMEOUT_SECONDS: int = 120
    AI_MAX_RETRIES: int = 3
    AI_APPROVAL_RECORD_THRESHOLD: int = 5
    AI_LOG_RETENTION_DAYS: int = 90

    # Upload Settings
    MAX_UPLOAD_FILE_SIZE_BYTES: int = 10 * 1024 * 1024
    ALLOWED_UPLOAD_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "text/plain",
        "application/zip",
    ]

    # ── Email & SMTP Configuration ──────────────────────────────────────────
    SMTP_TLS: bool = True
    SMTP_PORT: int = 587
    SMTP_HOST: Optional[str] = "s.mail25.info"
    SMTP_USER: Optional[str] = "no-reply@winvinaya.com"
    SMTP_PASSWORD: Optional[str] = "Admin##2025@"
    EMAILS_FROM_EMAIL: str = "no-reply@winvinaya.com"
    EMAILS_FROM_NAME: str = "winvinaya"
    EMAIL_NOTIFICATIONS_ENABLED: bool = True
    TIMESHEET_SUBMISSION_EMAIL: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
