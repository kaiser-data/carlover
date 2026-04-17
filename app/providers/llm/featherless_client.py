from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI
from loguru import logger

from app.config import Settings, get_settings
from app.providers.llm.base import BaseLLMProvider


class FeatherlessClient(BaseLLMProvider):
    """
    LLM provider backed by Featherless AI (OpenAI-compatible API).

    Uses langchain-openai's ChatOpenAI with a custom base_url.
    Retry and timeout are delegated to ChatOpenAI internally —
    do NOT add additional manual retry logic on top.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_chat_model(self, model_name: str, **kwargs: Any) -> ChatOpenAI:
        """
        Return a ChatOpenAI instance pointed at Featherless.

        Args:
            model_name: Exact model identifier as accepted by Featherless.
            **kwargs: Additional kwargs forwarded to ChatOpenAI (e.g. temperature).
        """
        logger.debug(f"Creating Featherless chat model: {model_name}")
        return ChatOpenAI(
            model=model_name,
            base_url=self.settings.FEATHERLESS_BASE_URL,
            api_key=self.settings.FEATHERLESS_API_KEY,
            timeout=self.settings.LLM_TIMEOUT,
            max_retries=self.settings.LLM_MAX_RETRIES,
            **kwargs,
        )


@lru_cache(maxsize=1)
def get_llm_provider() -> FeatherlessClient:
    """Return cached FeatherlessClient instance."""
    return FeatherlessClient()
