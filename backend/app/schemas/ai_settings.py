"""AI Engine — Settings Response Schemas"""

from __future__ import annotations
from pydantic import BaseModel


class AISettingItem(BaseModel):
    key: str
    value: str | None
    description: str
    is_secret: bool
    is_set: bool


class AISettingsResponse(BaseModel):
    settings: list[AISettingItem]
    active_provider: str
    providers: list[dict]
    supported_providers: list[str]


class AISettingsSaveRequest(BaseModel):
    """Batch save — only provided keys are updated."""
    AI_ENABLED: str | None = None
    AI_PROVIDER: str | None = None
    AI_MODEL_OVERRIDE: str | None = None
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    MISTRAL_API_KEY: str | None = None
    TOGETHER_API_KEY: str | None = None
    COHERE_API_KEY: str | None = None
    OLLAMA_BASE_URL: str | None = None
    OLLAMA_MODEL: str | None = None


class AIConnectionTestRequest(BaseModel):
    provider: str
    api_key: str | None = None


class AIConnectionTestResponse(BaseModel):
    success: bool
    provider: str
    model: str
    message: str
    latency_ms: int | None = None
