"""AI Engine — Runtime Settings Management Endpoints"""

from __future__ import annotations

import logging
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.ai.providers import SUPPORTED_PROVIDERS, get_provider_info, get_llm_provider
from app.ai.brain.exceptions import LLMAuthError, LLMProviderError
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.system_setting import SystemSetting
from app.repositories.system_setting_repository import SystemSettingRepository
from app.schemas.ai_settings import (
    AISettingItem,
    AISettingsResponse,
    AISettingsSaveRequest,
    AIConnectionTestRequest,
    AIConnectionTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

AI_SETTING_DEFINITIONS: dict[str, tuple[str, bool, str]] = {
    "AI_ENABLED": ("Enable or disable the AI Engine", False, "true"),
    "AI_PROVIDER": ("Active LLM provider", False, "anthropic"),
    "AI_FALLBACK_PROVIDER": ("Secondary fallback LLM provider", False, "gemini"),
    "AI_MODEL_OVERRIDE": ("Override the default model for the active provider", False, ""),
    "ANTHROPIC_API_KEY": ("Anthropic API Key (Claude)", True, ""),
    "GEMINI_API_KEY": ("Google Gemini API Key", True, ""),
    "OPENAI_API_KEY": ("OpenAI API Key (ChatGPT)", True, ""),
    "MISTRAL_API_KEY": ("Mistral AI API Key", True, ""),
    "TOGETHER_API_KEY": ("Together AI API Key", True, ""),
    "COHERE_API_KEY": ("Cohere API Key", True, ""),
    "OLLAMA_BASE_URL": ("Ollama server base URL", False, "http://localhost:11434"),
    "OLLAMA_MODEL": ("Ollama model name", False, "llama3.1"),
}

SECRET_MASK = "••••••••"


@router.get(
    "",
    response_model=AISettingsResponse,
    summary="Get AI Harness Engine settings",
)
async def get_ai_settings(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> AISettingsResponse:
    repo = SystemSettingRepository(db)
    all_settings = await repo.get_all_settings(organization_id=current_user.organization_id)
    settings_map = {s.key: s for s in all_settings}

    items = []
    for key, (description, is_secret, _default) in AI_SETTING_DEFINITIONS.items():
        stored = settings_map.get(key)
        raw_value = stored.value if stored else None
        is_set = bool(raw_value and raw_value.strip())
        display_value = SECRET_MASK if (is_secret and is_set) else raw_value

        items.append(
            AISettingItem(
                key=key,
                value=display_value,
                description=description,
                is_secret=is_secret,
                is_set=is_set,
            )
        )

    provider_setting = settings_map.get("AI_PROVIDER")
    active_provider = (
        provider_setting.value
        if provider_setting and provider_setting.value
        else settings.AI_PROVIDER
    )

    return AISettingsResponse(
        settings=items,
        active_provider=active_provider,
        providers=get_provider_info(),
        supported_providers=SUPPORTED_PROVIDERS,
    )


@router.put(
    "",
    summary="Save AI Harness Engine settings",
    status_code=status.HTTP_200_OK,
)
async def save_ai_settings(
    body: AISettingsSaveRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(
        deps.require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
) -> dict:
    repo = SystemSettingRepository(db)
    all_settings = await repo.get_all_settings(organization_id=current_user.organization_id)
    settings_map = {s.key: s for s in all_settings if s.organization_id == current_user.organization_id}

    updates = body.model_dump(exclude_none=True)
    saved_keys = []

    for key, value in updates.items():
        if key not in AI_SETTING_DEFINITIONS:
            continue
        if value == SECRET_MASK:
            continue

        description, is_secret, _ = AI_SETTING_DEFINITIONS[key]

        if key in settings_map:
            existing = settings_map[key]
            existing.value = value
            await db.flush()
        else:
            new_s = SystemSetting(
                organization_id=current_user.organization_id,
                key=key,
                value=value,
                description=description,
                is_secret=is_secret,
            )
            db.add(new_s)
            await db.flush()

        saved_keys.append(key)

    await db.commit()
    return {
        "message": f"Saved {len(saved_keys)} setting(s) successfully.",
        "saved_keys": saved_keys,
    }


@router.post(
    "/test-connection",
    response_model=AIConnectionTestResponse,
    summary="Test LLM provider connection",
)
async def test_connection(
    body: AIConnectionTestRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> AIConnectionTestResponse:
    provider_name = body.provider.lower().strip()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider_name}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}",
        )

    if body.api_key and body.api_key != SECRET_MASK:
        key_attr_map = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "together": "TOGETHER_API_KEY",
            "cohere": "COHERE_API_KEY",
        }
        attr = key_attr_map.get(provider_name)
        if attr:
            setattr(settings, attr, body.api_key)

    try:
        provider = await get_llm_provider(
            db,
            override=provider_name,
            organization_id=current_user.organization_id,
        )
        start = time.monotonic()
        await provider.complete(
            system_prompt="You are a test assistant. Reply with valid JSON only.",
            user_message='{"test": true}',
            temperature=0,
            max_tokens=20,
        )
        latency = int((time.monotonic() - start) * 1000)

        return AIConnectionTestResponse(
            success=True,
            provider=provider_name,
            model=provider.model_name,
            message=f"Connection successful. Model responded in {latency}ms.",
            latency_ms=latency,
        )
    except LLMAuthError:
        return AIConnectionTestResponse(
            success=False,
            provider=provider_name,
            model="",
            message="Authentication failed. Please check your API key.",
        )
    except LLMProviderError as e:
        return AIConnectionTestResponse(
            success=False,
            provider=provider_name,
            model="",
            message=f"Connection failed: {e.message}",
        )
    except Exception as e:
        return AIConnectionTestResponse(
            success=False,
            provider=provider_name,
            model="",
            message=f"Unexpected error: {str(e)[:200]}",
        )
