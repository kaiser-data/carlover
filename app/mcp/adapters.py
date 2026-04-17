"""
MCP Tool Adapters — wrap MCP tool schemas into agent-callable functions.

Each adapter:
1. Takes a dict of parameters
2. Calls the underlying MCP tool
3. Returns a typed result

Register adapters in the MCPRegistry at startup.
"""
from __future__ import annotations

from typing import Any


async def example_adapter(params: dict[str, Any]) -> dict[str, Any]:
    """
    Example MCP tool adapter.
    Replace with real MCP client call when integrating external tools.
    """
    # TODO: Replace with actual MCP tool invocation
    return {"result": f"example tool called with params: {params}", "source": "mcp_example"}
