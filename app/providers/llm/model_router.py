from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.providers.llm.featherless_client import get_llm_provider

TaskType = Literal["orchestrator", "reasoning", "vision", "response"]


class ModelRouter:
    """Maps task types to model names based on the active LLM provider."""

    def get_model(self, task: TaskType, **kwargs) -> ChatOpenAI:
        """Return a chat model configured for the given task type."""
        settings = get_settings()
        model_name = settings.active_llm_config()["models"][task]
        return get_llm_provider().get_chat_model(model_name, **kwargs)


_router = ModelRouter()


def get_model(task: TaskType, **kwargs) -> ChatOpenAI:
    """Module-level convenience wrapper around ModelRouter."""
    return _router.get_model(task, **kwargs)
