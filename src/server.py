"""FastAPI Application providing dual MCP (SSE & Streamable HTTP) and REST OpenAPI Interfaces.

Orchestrates:
- REST API (ChatGPT Custom GPT Actions, monitoring) via src.api.routes_rest
- Model Context Protocol (Claude Code, Antigravity, Cursor) via src.api.routes_mcp
- Business logic via src.services.election_service
- Configuration via src.config.settings
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_mcp import router as mcp_router
from src.api.routes_rest import router as rest_router
from src.config import settings
from src.mcp.tools import handle_call_tool, handle_list_tools, mcp_server
from src.services.election_service import election_service

# Logging setup parameterized via settings
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp_volby_2026")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing index initialization and connection teardown."""
    await election_service.initialize()
    yield
    await election_service.shutdown()


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount modular routers
    app.include_router(rest_router)
    app.include_router(mcp_router)

    return app


# Default application instance
app = create_app()


def run():
    """Runs the server using uvicorn."""
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )


# Re-exports for backwards compatibility
__all__ = [
    "app",
    "create_app",
    "mcp_server",
    "handle_list_tools",
    "handle_call_tool",
    "election_service",
    "run",
]

if __name__ == "__main__":
    run()
