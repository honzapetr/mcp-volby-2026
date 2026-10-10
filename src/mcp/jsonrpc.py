"""JSON-RPC 2.0 Dispatcher for Streamable HTTP MCP Clients (e.g. Antigravity IDE, Cursor)."""

import uuid
from typing import Optional

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from src.config import settings
from src.core.security import verify_mcp_auth
from src.mcp.tools import handle_call_tool, handle_list_tools


async def dispatch_jsonrpc(req: dict) -> Optional[dict]:
    """Processes a single JSON-RPC 2.0 request or notification."""
    jsonrpc_ver = req.get("jsonrpc", "2.0")
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    # Notifications do not have an "id" and do not expect a response
    is_notification = req_id is None

    if method == "initialize":
        client_proto = params.get("protocolVersion", "2024-11-05")
        result = {
            "protocolVersion": client_proto,
            "capabilities": {
                "tools": {
                    "listChanged": False
                }
            },
            "serverInfo": {
                "name": settings.MCP_SERVER_NAME,
                "version": settings.APP_VERSION,
            }
        }
        return {"jsonrpc": jsonrpc_ver, "id": req_id, "result": result}

    elif method in ("notifications/initialized", "notifications/cancelled"):
        return None

    elif method == "ping":
        return {"jsonrpc": jsonrpc_ver, "id": req_id, "result": {}}

    elif method == "tools/list":
        tools = await handle_list_tools()
        tools_data = [t.model_dump() for t in tools]
        return {"jsonrpc": jsonrpc_ver, "id": req_id, "result": {"tools": tools_data}}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}
        content_items = await handle_call_tool(tool_name, arguments)
        content_data = [c.model_dump() for c in content_items]
        return {
            "jsonrpc": jsonrpc_ver,
            "id": req_id,
            "result": {
                "content": content_data,
                "isError": False
            }
        }

    elif method == "prompts/list":
        return {"jsonrpc": jsonrpc_ver, "id": req_id, "result": {"prompts": []}}

    elif method == "resources/list":
        return {"jsonrpc": jsonrpc_ver, "id": req_id, "result": {"resources": []}}

    elif method == "resources/templates/list":
        return {"jsonrpc": jsonrpc_ver, "id": req_id, "result": {"resourceTemplates": []}}

    else:
        if is_notification:
            return None
        return {
            "jsonrpc": jsonrpc_ver,
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found"
            }
        }


async def handle_jsonrpc_endpoint(request: Request) -> Response:
    """Handles Streamable HTTP / JSON-RPC 2.0 MCP requests."""
    verify_mcp_auth(request)

    session_id = request.headers.get("mcp-session-id") or request.query_params.get("session_id") or str(uuid.uuid4())

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON formát v těle požadavku.")

    resp_headers = {
        "mcp-session-id": session_id,
        "content-type": "application/json"
    }

    if isinstance(body, list):
        responses = []
        for item in body:
            res = await dispatch_jsonrpc(item)
            if res is not None:
                responses.append(res)
        return JSONResponse(content=responses, headers=resp_headers)
    elif isinstance(body, dict):
        res = await dispatch_jsonrpc(body)
        if res is None:
            return Response(status_code=204, headers=resp_headers)
        return JSONResponse(content=res, headers=resp_headers)
    else:
        raise HTTPException(status_code=400, detail="Očekáván JSON objekt nebo pole.")
