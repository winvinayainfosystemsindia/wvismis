import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.ai.brain.exceptions import LLMProviderError
from app.repositories.system_setting_repository import SystemSettingRepository
from app.ai.providers.base import LLMProvider
from app.ai.providers.fallback import FallbackLLMProvider

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = [
    "anthropic",
    "claude",
    "gemini",
    "openai",
    "mistral",
    "together",
    "cohere",
    "ollama",
]


def get_provider_registry():
    from app.ai.providers.anthropic import AnthropicProvider
    from app.ai.providers.gemini import GeminiProvider
    from app.ai.providers.openai import OpenAIProvider
    from app.ai.providers.mistral import MistralProvider

    return {
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "mistral": MistralProvider,
    }


PROVIDER_REGISTRY = get_provider_registry()


async def get_llm_provider(
    db: Optional[AsyncSession] = None,
    override: str | None = None,
    organization_id: Optional[int] = None,
) -> LLMProvider:
    repo = SystemSettingRepository(db) if db is not None else None
    registry = get_provider_registry()

    # If specific override is requested (e.g. testing connection)
    if override:
        provider_name = override.lower().strip()
        if provider_name == "claude":
            provider_name = "anthropic"
        if provider_name not in registry:
            raise LLMProviderError(
                f"Unknown or unsupported AI provider '{provider_name}'.",
                provider=provider_name,
            )
        provider_class = registry[provider_name]
        api_key = None
        model_override = None
        if repo:
            key_field = f"{provider_name.upper()}_API_KEY"
            stored_key = await repo.get_by_key(key_field, organization_id=organization_id)
            api_key = stored_key.value.strip() if stored_key and stored_key.value else None

            provider_override_key = f"AI_MODEL_{provider_name.upper()}_OVERRIDE"
            stored_provider_model = await repo.get_by_key(
                provider_override_key,
                organization_id=organization_id,
            )
            model_override = stored_provider_model.value if stored_provider_model and stored_provider_model.value else None
        return provider_class(api_key=api_key, model=model_override)

    # Standard resolution
    stored_provider = await repo.get_by_key("AI_PROVIDER", organization_id=organization_id) if repo else None
    provider_name = (
        stored_provider.value.strip().lower()
        if stored_provider and stored_provider.value
        else settings.AI_PROVIDER.strip().lower()
    )
    if provider_name == "claude":
        provider_name = "anthropic"

    if provider_name not in registry:
        raise LLMProviderError(
            f"Unknown or unsupported AI provider '{provider_name}'.",
            provider=provider_name,
        )

    # Primary provider
    primary_cls = registry[provider_name]
    primary_api_key = None
    primary_model = None
    if repo:
        primary_key_field = f"{provider_name.upper()}_API_KEY"
        stored_primary_key = await repo.get_by_key(primary_key_field, organization_id=organization_id)
        primary_api_key = stored_primary_key.value.strip() if stored_primary_key and stored_primary_key.value else None

        primary_model_override = await repo.get_by_key(
            f"AI_MODEL_{provider_name.upper()}_OVERRIDE",
            organization_id=organization_id,
        )
        primary_model = primary_model_override.value if primary_model_override and primary_model_override.value else None

    primary_instance = primary_cls(api_key=primary_api_key, model=primary_model)

    # Fallback provider setup
    fallback_name = getattr(settings, "AI_FALLBACK_PROVIDER", "gemini").lower().strip()
    if fallback_name == "claude":
        fallback_name = "anthropic"

    if fallback_name and fallback_name != provider_name and fallback_name in registry:
        fallback_cls = registry[fallback_name]
        fallback_api_key = None
        fallback_model = None
        if repo:
            fallback_key_field = f"{fallback_name.upper()}_API_KEY"
            stored_fallback_key = await repo.get_by_key(fallback_key_field, organization_id=organization_id)
            fallback_api_key = stored_fallback_key.value.strip() if stored_fallback_key and stored_fallback_key.value else None

            fallback_model_override = await repo.get_by_key(
                f"AI_MODEL_{fallback_name.upper()}_OVERRIDE",
                organization_id=organization_id,
            )
            fallback_model = fallback_model_override.value if fallback_model_override and fallback_model_override.value else None

        try:
            fallback_instance = fallback_cls(api_key=fallback_api_key, model=fallback_model)
            return FallbackLLMProvider(primary=primary_instance, fallback=fallback_instance)
        except Exception as e:
            logger.warning("Could not initialize fallback LLM provider '%s': %s", fallback_name, e)
            return primary_instance

    return primary_instance


def get_provider_info() -> list[dict]:
    """Returns metadata about all supported providers for /ai/health."""
    provider_key_map = {
        "anthropic": ("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY),
        "gemini": ("GEMINI_API_KEY", settings.GEMINI_API_KEY),
        "openai": ("OPENAI_API_KEY", settings.OPENAI_API_KEY),
        "mistral": ("MISTRAL_API_KEY", settings.MISTRAL_API_KEY),
        "together": ("TOGETHER_API_KEY", settings.TOGETHER_API_KEY),
        "cohere": ("COHERE_API_KEY", settings.COHERE_API_KEY),
        "ollama": ("OLLAMA_BASE_URL", settings.OLLAMA_BASE_URL),
    }
    model_map = {
        "anthropic": settings.AI_MODEL_ANTHROPIC,
        "gemini": settings.AI_MODEL_GEMINI,
        "openai": settings.AI_MODEL_OPENAI,
        "mistral": settings.AI_MODEL_MISTRAL,
        "together": settings.AI_MODEL_TOGETHER,
        "cohere": settings.AI_MODEL_COHERE,
        "ollama": settings.OLLAMA_MODEL,
    }

    result = []
    for name in [p for p in SUPPORTED_PROVIDERS if p != "claude"]:
        key_name, key_value = provider_key_map.get(name, ("UNKNOWN", None))
        result.append({
            "name": name,
            "is_active": name == settings.AI_PROVIDER,
            "configured": bool(key_value),
            "model": model_map.get(name, "unknown"),
            "key_env_var": key_name,
        })
    return result
