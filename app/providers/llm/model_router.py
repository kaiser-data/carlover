from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.providers.llm.featherless_client import get_llm_provider

TaskType = Literal["orchestrator", "reasoning", "vision", "response"]


class ModelRouter:
    """Maps task types to specific model names from ENV and returns configured models."""

    _task_to_env: dict[TaskType, str] = {
        "orchestrator": "FEATHERLESS_MODEL_ORCHESTRATOR",
        "reasoning": "FEATHERLESS_MODEL_REASONING",
        "vision": "FEATHERLESS_MODEL_VISION",
        "response": "FEATHERLESS_MODEL_RESPONSE",
    }

    def get_model(self, task: TaskType, **kwargs) -> ChatOpenAI:
        """Return a chat model configured for the given task type."""
        settings = get_settings()
        model_name = getattr(settings, self._task_to_env[task])
        return get_llm_provider().get_chat_model(model_name, **kwargs)


_router = ModelRouter()


def get_model(task: TaskType, **kwargs) -> ChatOpenAI:
    """Module-level convenience wrapper around ModelRouter."""
    return _router.get_model(task, **kwargs)
