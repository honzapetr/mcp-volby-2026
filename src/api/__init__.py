"""API routers layer."""

from src.api.routes_mcp import router as mcp_router
from src.api.routes_rest import router as rest_router

__all__ = ["rest_router", "mcp_router"]
