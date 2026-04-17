"""
AGENT_REGISTRY maps agent names to their async callable (state → AgentOutput).

Using a registry avoids direct imports in graph.py and nodes.py,
preventing circular import issues. Populate lazily on first access.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from app.graph.state import CarAssistantState


def _build_registry() -> dict[str, Callable]:
    from app.agents.adac_agent import run_adac_agent
    from app.agents.image_agent import run_image_agent
    from app.agents.sandbox_agent import run_sandbox_agent
    from app.agents.supabase_agent import run_supabase_agent

    return {
        "adac": run_adac_agent,
        "supabase": run_supabase_agent,
        "image": run_image_agent,
        "sandbox": run_sandbox_agent,
    }


_registry: dict[str, Callable] | None = None


def get_registry() -> dict[str, Callable]:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry
