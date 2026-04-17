from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_openai import ChatOpenAI


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers. Swap implementations without changing agents."""

    @abstractmethod
    def get_chat_model(self, model_name: str, **kwargs: Any) -> ChatOpenAI:
        """Return a configured ChatOpenAI-compatible chat model."""
        ...
