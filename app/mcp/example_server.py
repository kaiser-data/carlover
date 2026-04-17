"""
Example MCP server — minimal demonstration of how to expose tools via MCP.

To activate:
1. Set MCP_ENABLED=true in .env
2. Install the mcp library: pip install mcp
3. Run this server: python -m app.mcp.example_server
4. Register its tools in app/mcp/registry.py

See https://github.com/anthropics/mcp for full MCP documentation.
"""
from __future__ import annotations

# Minimal MCP server example (uncomment and adapt when mcp library is installed):
#
# from mcp.server import Server
# from mcp.server.stdio import stdio_server
# from mcp.types import TextContent, Tool
#
# server = Server("carlover-mcp")
#
# @server.list_tools()
# async def list_tools():
#     return [
#         Tool(
#             name="get_vehicle_recall",
#             description="Fetch recall data for a vehicle from the KBA database",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "make": {"type": "string"},
#                     "model": {"type": "string"},
#                     "year": {"type": "integer"},
#                 },
#                 "required": ["make", "model"],
#             },
#         )
#     ]
#
# @server.call_tool()
# async def call_tool(name: str, arguments: dict):
#     if name == "get_vehicle_recall":
#         # TODO: Integrate with KBA recall database
#         return [TextContent(type="text", text="No recalls found (mock response)")]
#     raise ValueError(f"Unknown tool: {name}")
#
# async def main():
#     async with stdio_server() as streams:
#         await server.run(*streams, server.create_initialization_options())
#
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())

print("MCP example server — uncomment and configure to use.")
