"""FastAPI Router for REST OpenAPI Endpoints (ChatGPT Custom GPT, Monitoring, Webhooks)."""

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.config import settings
from src.core.security import verify_auth
from src.models import (
    CoalitionAnalysisResponse,
    CountingProgressResponse,
    ElectionOverviewResponse,
    MunicipalResultResponse,
    SearchResultResponse,
    SenateDistrictBreakdownResponse,
    SenateOverviewResponse,
)
from src.services.election_service import election_service

router = APIRouter()


@router.get("/health", tags=["Systém"])
async def health_check():
    """Healthcheck endpoint for Docker container, Caddy reverse proxy, and monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "mcp-volby-2026",
        "csu_base_url": settings.CSU_BASE_URL,
    }


@router.get(
    "/api/overview",
    response_model=ElectionOverviewResponse,
    tags=["Volby 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_overview():
    """Celkový stav voleb v ČR 2026 a postup sčítání."""
    return await election_service.get_overview()


@router.get(
    "/api/senat",
    response_model=SenateOverviewResponse,
    tags=["Senát 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_senat_all():
    """Výsledky voleb do Senátu za všech 27 volených obvodů."""
    return await election_service.get_senate_results()


@router.get(
    "/api/senat/{obvod}",
    response_model=SenateOverviewResponse,
    tags=["Senát 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_senat_district(obvod: str):
    """Výsledky voleb do Senátu za konkrétní senátní obvod (číslo obvodu nebo sídlo)."""
    return await election_service.get_senate_results(obvod)


@router.get(
    "/api/senat/{obvod}/obce",
    response_model=SenateDistrictBreakdownResponse,
    tags=["Senát 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_senat_district_breakdown(obvod: str):
    """Detailní výsledky senátních voleb po obcích v rámci obvodu."""
    return await election_service.get_senate_district_breakdown(obvod)


@router.get(
    "/api/obce/{obec}",
    response_model=MunicipalResultResponse,
    tags=["Komunální volby 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_municipal(obec: str):
    """Výsledky voleb do zastupitelstva konkrétní obce/města dle názvu nebo kódu."""
    return await election_service.get_municipal_results(obec)


@router.get(
    "/api/obce/{obec}/koalice",
    response_model=CoalitionAnalysisResponse,
    tags=["Komunální volby 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_coalition_scenarios(obec: str):
    """Analýza povolebních koaličních scénářů a minimálních vítězných koalic (MWC) pro obec."""
    return await election_service.get_coalition_scenarios(obec)


@router.get(
    "/api/search",
    response_model=SearchResultResponse,
    tags=["Vyhledávání"],
    dependencies=[Depends(verify_auth)],
)
async def api_search(
    q: str = Query(..., description="Hledaný název obce nebo obvodu"),
    limit: int = Query(settings.DEFAULT_SEARCH_LIMIT, description="Maximální počet výsledků"),
):
    """Vyhledávač obcí a senátních obvodů."""
    return await election_service.search(q, limit)


@router.get(
    "/api/progress",
    response_model=CountingProgressResponse,
    tags=["Telemetrie"],
    dependencies=[Depends(verify_auth)],
)
async def api_progress():
    """Aktuální tempo a průběh sčítání hlasů."""
    return await election_service.get_progress()
