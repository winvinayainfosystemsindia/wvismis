from typing import Any, AsyncGenerator
from abc import ABC, abstractmethod


class LLMResponse:
    """Structured response from any LLM provider."""

    def __init__(
        self,
        content: str,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
        raw_response: Any = None,
    ):
        self.content = content
        self.tokens_used = tokens_used
        self.cost_usd = cost_usd
        self.raw_response = raw_response


class LLMProvider(ABC):
    """Abstract interface every LLM provider adapter must implement."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...
