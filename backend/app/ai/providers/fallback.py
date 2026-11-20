import logging
from typing import AsyncGenerator
from app.ai.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class FallbackLLMProvider(LLMProvider):
    """
    Composite LLM provider that uses a primary provider (e.g. Anthropic Claude)
    and transparently falls back to a secondary provider (e.g. Google Gemini)
    if the primary fails due to rate-limiting, authentication, timeout, or API errors.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self._active: LLMProvider = primary

    @property
    def primary(self) -> LLMProvider:
        return self._primary

    @property
    def fallback(self) -> LLMProvider:
        return self._fallback

    @property
    def provider_name(self) -> str:
        return self._active.provider_name

    @property
    def model_name(self) -> str:
        return self._active.model_name

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            res = await self._primary.complete(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self._active = self._primary
            return res
        except Exception as primary_exc:
            logger.warning(
                "Primary AI Provider '%s' (%s) failed: %s. Falling back to '%s' (%s)...",
                self._primary.provider_name,
                self._primary.model_name,
                primary_exc,
                self._fallback.provider_name,
                self._fallback.model_name,
            )
            self._active = self._fallback
            try:
                res = await self._fallback.complete(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return res
            except Exception as fallback_exc:
                logger.error(
                    "Fallback AI Provider '%s' also failed: %s",
                    self._fallback.provider_name,
                    fallback_exc,
                )
                raise fallback_exc

    async def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        try:
            self._active = self._primary
            async for token in self._primary.stream_complete(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield token
        except Exception as primary_exc:
            logger.warning(
                "Primary AI Provider '%s' stream failed: %s. Falling back to '%s'...",
                self._primary.provider_name,
                primary_exc,
                self._fallback.provider_name,
            )
            self._active = self._fallback
            async for token in self._fallback.stream_complete(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield token
