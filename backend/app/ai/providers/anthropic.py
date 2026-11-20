import httpx
import logging
from typing import AsyncGenerator
from app.core.config import settings
from app.ai.brain.exceptions import LLMAuthError, LLMProviderError, LLMRateLimitError
from app.ai.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Adapter with Sonnet model support."""

    BASE_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.ANTHROPIC_API_KEY
        self._raw_model = model or settings.AI_MODEL_ANTHROPIC
        self._models = [m.strip() for m in self._raw_model.split(",") if m.strip()]
        if not self._models:
            self._models = ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022"]
        self._model = self._models[0]
        if not self._api_key:
            raise LLMAuthError("anthropic")

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        candidate_models = list(self._models)
        for backup_sonnet in ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-sonnet-latest"]:
            if backup_sonnet not in candidate_models:
                candidate_models.append(backup_sonnet)

        last_error = ""
        for model_candidate in candidate_models:
            payload = {
                "model": model_candidate,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(self.BASE_URL, json=payload, headers=headers)
                    if resp.status_code == 429:
                        raise LLMRateLimitError(provider="anthropic")
                    if resp.status_code in (401, 403):
                        raise LLMAuthError("anthropic")
                    if not resp.is_success:
                        last_error = resp.text
                        logger.warning(
                            "Anthropic model '%s' failed (%s): %s. Trying next candidate...",
                            model_candidate,
                            resp.status_code,
                            resp.text[:200],
                        )
                        continue

                    data = resp.json()
                    content = data["content"][0]["text"]
                    self._model = model_candidate
                    return LLMResponse(content=content, raw_response=data)
            except (LLMRateLimitError, LLMAuthError):
                raise
            except Exception as e:
                last_error = str(e)
                logger.warning("Anthropic request to '%s' failed: %s", model_candidate, e)
                continue

        raise LLMProviderError(f"Anthropic error: {last_error}", provider="anthropic")

    async def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        res = await self.complete(system_prompt, user_message, temperature, max_tokens)
        yield res.content
