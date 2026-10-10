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
    PrecinctSpeedResponse,
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
async def api_senat_all(
    detail_level: str = Query(settings.DEFAULT_SENATE_DETAIL, description="Úroveň detailu ('auto', 'summary', 'full')"),
    status_filter: Optional[str] = Query(None, description="Filtr stavu ('all', 'completed', 'in_progress', 'close_races')"),
):
    """Výsledky voleb do Senátu za všech 27 volených obvodů."""
    return await election_service.get_senate_results(
        detail_level=detail_level,
        status_filter=status_filter,
    )


@router.get(
    "/api/senat/{obvod}",
    response_model=SenateOverviewResponse,
    tags=["Senát 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_senat_district(
    obvod: str,
    detail_level: str = Query("full", description="Úroveň detailu ('auto', 'summary', 'full')"),
):
    """Výsledky voleb do Senátu za konkrétní senátní obvod (číslo obvodu nebo sídlo)."""
    return await election_service.get_senate_results(obvod, detail_level=detail_level)


@router.get(
    "/api/senat/{obvod}/obce",
    response_model=SenateDistrictBreakdownResponse,
    tags=["Senát 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_senat_district_breakdown(
    obvod: str,
    limit: int = Query(settings.DEFAULT_BREAKDOWN_LIMIT, description="Maximální počet obcí (0 pro všechny)"),
    obec: Optional[str] = Query(None, description="Filtr na konkrétní obec uvnitř obvodu"),
    sort_by: str = Query("voters", description="Řazení: 'voters', 'turnout', 'processed', 'name'"),
    summary_only: bool = Query(False, description="Pouze agregovaný souhrn"),
):
    """Detailní výsledky senátních voleb po obcích v rámci obvodu."""
    return await election_service.get_senate_district_breakdown(
        obvod=obvod,
        limit=limit,
        obec=obec,
        sort_by=sort_by,
        summary_only=summary_only,
    )


@router.get(
    "/api/obce/{obec}",
    response_model=MunicipalResultResponse,
    tags=["Komunální volby 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_municipal(
    obec: str,
    detail_level: str = Query(settings.DEFAULT_MUNICIPAL_DETAIL, description="Úroveň detailu ('parties', 'summary', 'elected', 'full')"),
    include_candidates: bool = Query(False, description="Zahrnout kompletní kandidátní listiny"),
    party: Optional[str] = Query(None, description="Filtr na kandidáty konkrétní strany"),
    top_parties: Optional[int] = Query(None, description="Omezení na N nejsilnějších stran"),
):
    """Výsledky voleb do zastupitelstva konkrétní obce/města dle názvu nebo kódu."""
    return await election_service.get_municipal_results(
        obec=obec,
        detail_level=detail_level,
        include_candidates=include_candidates,
        party=party,
        top_parties=top_parties,
    )


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


@router.get(
    "/api/okrsky/rychlost",
    response_model=PrecinctSpeedResponse,
    tags=["Okrsky a sčítání 2026"],
    dependencies=[Depends(verify_auth)],
)
async def api_precinct_speed(
    election_type: str = Query("obce", description="Typ voleb: 'obce' nebo 'senat'"),
    order: str = Query("slowest", description="Řazení: 'slowest' (nejpomalejší komise) nebo 'fastest' (nejrychlejší komise)"),
    obec: Optional[str] = Query(None, description="Filtr pro konkrétní obec (název nebo kód ČSÚ)"),
    obvod: Optional[str] = Query(None, description="Filtr pro senátní obvod (číslo nebo sídlo)"),
    okrsek: Optional[int] = Query(None, description="Konkrétní číslo volebního okrsku"),
    limit: int = Query(10, ge=1, le=100, description="Maximální počet vrácených okrsků"),
):
    """Zjišťuje časy zpracování a odevzdání zápisů okrskových volebních komisí (nejpomalejší/nejrychlejší komise)."""
    return await election_service.get_precinct_speed(
        election_type=election_type,
        order=order,
        obec=obec,
        obvod=obvod,
        okrsek=okrsek,
        limit=limit,
    )

