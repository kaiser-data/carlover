from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI
from loguru import logger

from app.config import Settings, get_settings
from app.providers.llm.base import BaseLLMProvider


class FeatherlessClient(BaseLLMProvider):
    """
    OpenAI-compatible LLM client — points at whichever provider LLM_PROVIDER
    selects (groq, featherless, ...). Kept under this name for back-compat.

    Retry and timeout are delegated to ChatOpenAI internally — do NOT add
    additional manual retry logic on top.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_chat_model(self, model_name: str, **kwargs: Any) -> ChatOpenAI:
        """Return a ChatOpenAI instance pointed at the active provider."""
        cfg = self.settings.active_llm_config()
        logger.debug(
            f"Creating {self.settings.LLM_PROVIDER} chat model: {model_name}"
        )
        return ChatOpenAI(
            model=model_name,
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            timeout=self.settings.LLM_TIMEOUT,
            max_retries=self.settings.LLM_MAX_RETRIES,
            **kwargs,
        )


@lru_cache(maxsize=1)
def get_llm_provider() -> FeatherlessClient:
    """Return cached LLM client instance."""
    return FeatherlessClient()
