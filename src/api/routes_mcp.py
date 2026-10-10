"""FastAPI Router for Model Context Protocol (MCP) Endpoints.

Supports:
- SSE Transport (GET /sse, POST /messages) for Claude Code, Cursor
- Streamable HTTP Transport (POST /sse, POST /mcp, POST /messages) for Antigravity IDE, Cursor
"""

from fastapi import APIRouter, Request
from mcp.server.sse import SseServerTransport

from src.core.security import verify_mcp_auth
from src.mcp.jsonrpc import handle_jsonrpc_endpoint
from src.mcp.tools import mcp_server

router = APIRouter(tags=["MCP"])

# SSE Transport instance
sse_transport = SseServerTransport("/messages")


@router.get("/sse")
async def handle_sse(request: Request):
    """MCP Server-Sent Events (SSE) endpoint for persistent AI client connections (e.g. Claude Code)."""
    verify_mcp_auth(request)

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


@router.post("/sse")
async def handle_sse_post(request: Request):
    """MCP Streamable HTTP POST endpoint for clients connecting directly via HTTP POST (e.g. Antigravity IDE)."""
    return await handle_jsonrpc_endpoint(request)


@router.get("/mcp")
async def handle_mcp_get(request: Request):
    """Alias for /sse for clients configuring /mcp endpoint."""
    return await handle_sse(request)


@router.post("/mcp")
async def handle_mcp_post(request: Request):
    """MCP Streamable HTTP endpoint (/mcp)."""
    return await handle_jsonrpc_endpoint(request)


@router.post("/messages")
async def handle_messages(request: Request):
    """MCP messages endpoint - handles both SSE post-messages and Streamable HTTP requests."""
    verify_mcp_auth(request)

    if request.query_params.get("session_id"):
        await sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )
        return
    return await handle_jsonrpc_endpoint(request)
