"""Security module: Bearer token authentication and request verification."""

from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import settings

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def verify_auth(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> bool:
    """Validates Bearer token if API_KEY is configured in settings.
    
    Used as a FastAPI dependency for protected REST routes.
    """
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


def verify_mcp_auth(request: Request) -> bool:
    """Validates Bearer token from header or query param for MCP endpoints."""
    if not settings.API_KEY:
        return True

    auth_header = request.headers.get("Authorization")
    auth_token = None
    if auth_header and auth_header.startswith("Bearer "):
        auth_token = auth_header[7:].strip()
    else:
        auth_token = request.query_params.get("token")

    if auth_token != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Neplatný autorizační token pro MCP rozhraní.",
        )
    return True
