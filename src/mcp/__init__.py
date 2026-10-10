"""MCP layer: Server, tool definitions, SSE and Streamable HTTP JSON-RPC."""

from src.mcp.jsonrpc import dispatch_jsonrpc, handle_jsonrpc_endpoint
from src.mcp.tools import handle_call_tool, handle_list_tools, mcp_server

__all__ = [
    "mcp_server",
    "handle_list_tools",
    "handle_call_tool",
    "dispatch_jsonrpc",
    "handle_jsonrpc_endpoint",
]
