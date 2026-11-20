import httpx
import json
import logging
from typing import AsyncGenerator
from app.core.config import settings
from app.ai.brain.exceptions import LLMAuthError, LLMProviderError, LLMRateLimitError
from app.ai.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini Adapter supporting multi-model fallbacks (e.g. gemini-3.6-flash, gemini-3.5-flash-lite)."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._raw_model = model or settings.AI_MODEL_GEMINI
        self._models = [m.strip() for m in self._raw_model.split(",") if m.strip()]
        if not self._models:
            self._models = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
        self._model = self._models[0]
        if not self._api_key:
            raise LLMAuthError("gemini")

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_candidate_models(self) -> list[str]:
        candidates = list(self._models)
        # Safety fallback to available stable generation models if experimental 3.6/3.5 endpoints return 404
        for fallback_m in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            if fallback_m not in candidates:
                candidates.append(fallback_m)
        return candidates

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        candidate_models = self._get_candidate_models()
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }

        last_error = ""
        async with httpx.AsyncClient(timeout=60.0) as client:
            for model_candidate in candidate_models:
                url = f"{self.BASE_URL}/{model_candidate}:generateContent?key={self._api_key}"
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 429:
                        last_error = f"Rate limit on {model_candidate}"
                        logger.warning("Gemini model '%s' rate limited. Trying next candidate...", model_candidate)
                        continue
                    if resp.status_code in (401, 403):
                        raise LLMAuthError("gemini")
                    if not resp.is_success:
                        last_error = resp.text
                        logger.warning(
                            "Gemini model '%s' returned HTTP %d: %s. Trying next candidate...",
                            model_candidate,
                            resp.status_code,
                            resp.text[:200],
                        )
                        continue

                    data = resp.json()
                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                    self._model = model_candidate
                    return LLMResponse(content=content, raw_response=data)
                except (LLMAuthError,):
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.warning("Gemini request to '%s' failed: %s", model_candidate, e)
                    continue

        raise LLMProviderError(f"Gemini error across models {candidate_models}: {last_error}", provider="gemini")

    async def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        candidate_models = self._get_candidate_models()
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "text/plain",
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for model_candidate in candidate_models:
                url = f"{self.BASE_URL}/{model_candidate}:streamGenerateContent?key={self._api_key}"
                try:
                    async with client.stream("POST", url, json=payload) as response:
                        if not response.is_success:
                            error_text = await response.aread()
                            logger.warning(
                                "Gemini streaming on '%s' failed (%d): %s. Trying next candidate...",
                                model_candidate,
                                response.status_code,
                                error_text[:200],
                            )
                            continue

                        self._model = model_candidate
                        async for line in response.aiter_lines():
                            if not line or line.strip() in ("[", "]"):
                                continue
                            try:
                                clean_line = line.strip().rstrip(",")
                                data = json.loads(clean_line)
                                token = data["candidates"][0]["content"]["parts"][0]["text"]
                                yield token
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                        return
                except Exception as e:
                    logger.warning("Gemini stream error on '%s': %s", model_candidate, e)
                    continue

        # If streaming failed on all models, fallback to complete
        res = await self.complete(system_prompt, user_message, temperature, max_tokens)
        yield res.content
