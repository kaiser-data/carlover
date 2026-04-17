"""
MCP Tool Registry — maps tool names to adapter callables.

All tools registered here are available to agents when MCP_ENABLED=true.
"""
from __future__ import annotations

from typing import Any, Callable

_registry: dict[str, Callable[..., Any]] = {}


def register_tool(name: str, fn: Callable[..., Any]) -> None:
    """Register an MCP tool adapter under a given name."""
    _registry[name] = fn


def get_tool(name: str) -> Callable[..., Any] | None:
    return _registry.get(name)


def list_tools() -> list[str]:
    return list(_registry.keys())
