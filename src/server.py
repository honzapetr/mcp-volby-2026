"""FastAPI Application providing dual MCP (SSE Transport) and REST OpenAPI Interfaces.

Supports:
- Claude Code, Antigravity, Cursor, Claude Desktop via /sse & /messages
- ChatGPT Custom GPT Actions via /openapi.json & /api/*
- Security: Optional Bearer token authentication (API_KEY)
- CORS, structured logging, healthchecks
"""

import asyncio
import datetime
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional


from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool

from src.client_csu import csu_client
from src.config import settings
from src.models import (
    CountingProgressResponse,
    ElectionOverviewResponse,
    MunicipalResultResponse,
    SearchResultResponse,
    SenateOverviewResponse,
)
from src.parsers.codebook_loader import codebook_index
from src.parsers.kv_parser import parse_kv_cr_overview, parse_municipal_results
from src.parsers.senat_parser import parse_senate_results

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp_volby_2026")

# Security setup
security = HTTPBearer(auto_error=False)


async def verify_auth(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
    """Validates Bearer token if API_KEY is set in settings."""
    if not settings.API_KEY:
        return True
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chybí autorizační Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Neplatný autorizační token.",
        )
    return True


# Core service functions reused by both MCP tools and REST endpoints
async def service_get_election_overview() -> ElectionOverviewResponse:
    """Retrieves high-level summary of all ongoing Czech 2026 elections."""
    now_iso = datetime.datetime.now().isoformat()
    senat_xml = await csu_client.get_senat_vysledky()
    senat_res = parse_senate_results(senat_xml)

    kv_cr_xml = await csu_client.get_kv_vysledky_cr()
    kv_summary = parse_kv_cr_overview(kv_cr_xml)

    # Determine if counting started
    counting_started = (
        senat_res.districts_completed > 0
        or any(d.turnout.precincts_processed > 0 for d in senat_res.districts)
        or kv_summary.get("precincts_processed", 0) > 0
    )

    senat_precincts_total = sum(d.turnout.precincts_total for d in senat_res.districts)
    senat_precincts_proc = sum(d.turnout.precincts_processed for d in senat_res.districts)
    senat_pct = (
        round((senat_precincts_proc / senat_precincts_total * 100), 2)
        if senat_precincts_total > 0
        else 0.0
    )

    return ElectionOverviewResponse(
        current_time=now_iso,
        counting_started=counting_started,
        senate_summary={
            "districts_total": senat_res.districts_total,
            "districts_completed": senat_res.districts_completed,
            "precincts_total": senat_precincts_total,
            "precincts_processed": senat_precincts_proc,
            "precincts_processed_pct": senat_pct,
        },
        municipal_summary=kv_summary,
        last_updated=senat_res.generated_at or kv_summary.get("generated_at", now_iso),
    )


async def service_get_senate_results(obvod: Optional[str | int] = None) -> SenateOverviewResponse:
    """Retrieves Senate results for all 27 contested districts or a specific one."""
    district_num = None
    if obvod is not None:
        district_num = codebook_index.resolve_senate_district(obvod)
        if district_num is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Senátní obvod '{obvod}' nebyl nalezen. Zadejte číslo obvodu (např. 3) nebo sídlo (např. Cheb).",
            )

    xml_root = await csu_client.get_senat_vysledky()
    return parse_senate_results(xml_root, target_district=district_num)


async def service_get_municipal_results(obec: str) -> MunicipalResultResponse:
    """Retrieves municipal election results for a given municipality code or name."""
    kod_zastup = codebook_index.resolve_municipality_code(obec)
    if not kod_zastup:
        # Try search suggestions
        search_res = codebook_index.search(obec, limit=5)
        suggestions = [f"{r.name} (kód: {r.code})" for r in search_res.results]
        detail_msg = f"Obec '{obec}' nebyla nalezena."
        if suggestions:
            detail_msg += f" Možná jste mysleli: {', '.join(suggestions)}"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail_msg)

    xml_root = await csu_client.get_kv_obec(kod_zastup)
    return parse_municipal_results(xml_root)


async def service_search(query: str, limit: int = 15) -> SearchResultResponse:
    """Searches municipalities and Senate districts."""
    return codebook_index.search(query, limit=limit)


async def service_get_progress() -> CountingProgressResponse:
    """Calculates counting telemetry and velocity metrics."""
    overview = await service_get_election_overview()
    senate_pct = overview.senate_summary.get("precincts_processed_pct", 0.0)
    kv_pct = overview.municipal_summary.get("precincts_processed_pct", 0.0)

    if not overview.counting_started:
        msg = "Volební místnosti jsou uzavřeny ve 14:00. Sčítání hlasů prozatím nezapočalo (0 % okrsků)."
    elif senate_pct == 100.0 and kv_pct == 100.0:
        msg = "Sčítání hlasů pro Senát i zastupitelstva obcí je kompletně dokončeno (100 % okrsků)."
    else:
        msg = f"Probíhá sčítání: Senát sečten z {senate_pct:.1f} %, obecní zastupitelstva sečtena z {kv_pct:.1f} %."

    return CountingProgressResponse(
        timestamp=datetime.datetime.now().isoformat(),
        counting_active=overview.counting_started,
        senate_pct=senate_pct,
        municipal_pct=kv_pct,
        status_message=msg,
    )


# MCP Server Definition
mcp_server = Server("volby-cr-2026")
sse_transport = SseServerTransport("/messages")


@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Exposes all tools to MCP clients."""
    return [
        Tool(
            name="get_election_overview",
            description=(
                "Získá celkový přehled o stavu voleb v ČR 2026 (Senát a obecní zastupitelstva). "
                "Vrací, zda již začalo sčítání (sobota po 14:00), celkovou účast a procento sečtených okrsků."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_senate_results",
            description=(
                "Získá výsledky voleb do Senátu Parlamentu ČR 2026 (1. kolo, obměna 27 obvodů). "
                "Parametr 'obvod' je volitelný: číslo obvodu (např. 3) nebo název sídla (např. 'Cheb', 'Praha 5', 'Brno'). "
                "Pokud parametr nezadáte, vrátí souhrn všech 27 volených obvodů."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "obvod": {
                        "type": ["string", "integer"],
                        "description": "Číslo senátního obvodu (např. 3) nebo název sídla (např. 'Cheb', 'Praha 5').",
                    }
                },
            },
        ),
        Tool(
            name="get_municipal_results",
            description=(
                "Získá výsledky voleb do zastupitelstva konkrétní obce nebo města (komunální volby 2026). "
                "Uveďte název obce (např. 'Praha', 'Brno', 'Ostrava', 'Plzeň') nebo šestimístný kód obce ČSÚ (např. '554782'). "
                "Vrací volební účast, počet volených zastupitelů, % sečtených okrsků a výsledky kandidujících stran včetně mandátů."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "obec": {
                        "type": "string",
                        "description": "Název obce (např. 'Praha', 'Brno') nebo 6místný kód obce ČSÚ (např. '554782').",
                    }
                },
                "required": ["obec"],
            },
        ),
        Tool(
            name="search_municipality_or_district",
            description=(
                "Vyhledá obec nebo senátní obvod podle názvu či části názvu. "
                "Užitečné pro nalezení správného kódu obce nebo čísla senátního obvodu."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Hledaný název (např. 'Pardubice', 'Cheb', 'Praha 10').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximální počet výsledků (výchozí 15).",
                        "default": 15,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_live_counting_progress",
            description=(
                "Získá živou telemetrii sčítání hlasů od 14:00 (procento sečtených okrsků pro Senát a Obce, "
                "aktuální tempo sčítání a stavové hlášení)."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handles tool invocations from MCP clients."""
    try:
        if name == "get_election_overview":
            res = await service_get_election_overview()
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_senate_results":
            obvod = arguments.get("obvod")
            res = await service_get_senate_results(obvod)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_municipal_results":
            obec = arguments.get("obec")
            if not obec:
                return [TextContent(type="text", text="Chyba: Chybí povinný parametr 'obec'.")]
            res = await service_get_municipal_results(obec)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "search_municipality_or_district":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", 15))
            res = await service_search(query, limit)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_live_counting_progress":
            res = await service_get_progress()
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        else:
            return [TextContent(type="text", text=f"Chyba: Neznámý nástroj '{name}'.")]

    except HTTPException as exc:
        return [TextContent(type="text", text=f"Chyba: {exc.detail}")]
    except Exception as exc:
        logger.exception("Chyba při volání nástroje %s: %s", name, exc)
        return [TextContent(type="text", text=f"Interní chyba při zpracování požadavku: {exc}")]


# FastAPI Application Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes index on startup and cleans up HTTP client on shutdown."""
    logger.info("Initializing Election Codebooks Index...")
    codebook_index.initialize_defaults()
    # Asynchronously load full codebooks in background without blocking startup
    asyncio.create_task(codebook_index.load_remote_codebooks())
    yield
    logger.info("Shutting down CSU HTTP client...")
    await csu_client.close()


# FastAPI App
app = FastAPI(
    title="MCP Server pro Volby 2026 v ČR",
    description=(
        "Model Context Protocol (MCP) server a REST API pro živé výsledky voleb v České republice 2026 "
        "(Volby do Senátu Parlamentu ČR a volby do zastupitelstev obcí) ze sčítání ČSÚ (volby.cz / volby.gov.cz)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# REST Endpoints
@app.get("/health", tags=["Systém"])
async def health_check():
    """Healthcheck endpoint for Docker container and monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "mcp-volby-2026",
        "csu_base_url": settings.CSU_BASE_URL,
    }


@app.get("/api/overview", response_model=ElectionOverviewResponse, tags=["Volby 2026"], dependencies=[Depends(verify_auth)])
async def api_overview():
    """Celkový stav voleb v ČR 2026 a postup sčítání."""
    return await service_get_election_overview()


@app.get("/api/senat", response_model=SenateOverviewResponse, tags=["Senát 2026"], dependencies=[Depends(verify_auth)])
async def api_senat_all():
    """Výsledky voleb do Senátu za všech 27 volených obvodů."""
    return await service_get_senate_results()


@app.get("/api/senat/{obvod}", response_model=SenateOverviewResponse, tags=["Senát 2026"], dependencies=[Depends(verify_auth)])
async def api_senat_district(obvod: str):
    """Výsledky voleb do Senátu za konkrétní senátní obvod (číslo obvodu nebo sídlo)."""
    return await service_get_senate_results(obvod)


@app.get("/api/obce/{obec}", response_model=MunicipalResultResponse, tags=["Komunální volby 2026"], dependencies=[Depends(verify_auth)])
async def api_municipal(obec: str):
    """Výsledky voleb do zastupitelstva konkrétní obce/města dle názvu nebo kódu."""
    return await service_get_municipal_results(obec)


@app.get("/api/search", response_model=SearchResultResponse, tags=["Vyhledávání"], dependencies=[Depends(verify_auth)])
async def api_search(q: str = Query(..., description="Hledaný název obce nebo obvodu"), limit: int = 15):
    """Vyhledávač obcí a senátních obvodů."""
    return await service_search(q, limit)


@app.get("/api/progress", response_model=CountingProgressResponse, tags=["Telemetrie"], dependencies=[Depends(verify_auth)])
async def api_progress():
    """Aktuální tempo a průběh sčítání hlasů."""
    return await service_get_progress()


# JSON-RPC 2.0 Dispatcher for Streamable HTTP MCP Clients (e.g. Antigravity IDE, Cursor)
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
                "name": "volby-cr-2026",
                "version": "1.0.0"
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
    if settings.API_KEY:
        auth_header = request.headers.get("Authorization")
        auth_token = None
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()
        else:
            auth_token = request.query_params.get("token")
        if auth_token != settings.API_KEY:
            raise HTTPException(status_code=403, detail="Neplatný autorizační token pro MCP.")

    import uuid
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


# MCP Protocol Endpoints (Dual Transport: SSE & Streamable HTTP)
@app.get("/sse", tags=["MCP"])
async def handle_sse(request: Request):
    """MCP Server-Sent Events (SSE) endpoint for persistent AI client connection (e.g. Claude Code)."""
    # Check auth query param or header if API_KEY configured
    if settings.API_KEY:
        auth_header = request.headers.get("Authorization")
        auth_token = None
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()
        else:
            auth_token = request.query_params.get("token")
        if auth_token != settings.API_KEY:
            raise HTTPException(status_code=403, detail="Neplatný autorizační token pro MCP.")

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


@app.post("/sse", tags=["MCP"])
async def handle_sse_post(request: Request):
    """MCP Streamable HTTP POST endpoint for clients connecting directly via HTTP POST (e.g. Antigravity IDE)."""
    return await handle_jsonrpc_endpoint(request)


@app.get("/mcp", tags=["MCP"])
async def handle_mcp_get(request: Request):
    """Alias for /sse for clients configuring /mcp endpoint."""
    return await handle_sse(request)


@app.post("/mcp", tags=["MCP"])
async def handle_mcp_post(request: Request):
    """MCP Streamable HTTP endpoint (/mcp)."""
    return await handle_jsonrpc_endpoint(request)


@app.post("/messages", tags=["MCP"])
async def handle_messages(request: Request):
    """MCP messages endpoint - handles both SSE post-messages and Streamable HTTP."""
    if settings.API_KEY:
        auth_header = request.headers.get("Authorization")
        auth_token = None
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()
        else:
            auth_token = request.query_params.get("token")
        if auth_token != settings.API_KEY:
            raise HTTPException(status_code=403, detail="Neplatný autorizační token pro MCP.")

    if request.query_params.get("session_id"):
        await sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )
        return
    return await handle_jsonrpc_endpoint(request)


def run():
    """Runs the server using uvicorn."""
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )


if __name__ == "__main__":
    run()
