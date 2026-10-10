"""Election Service: Centralized business logic for processing Czech 2026 election data."""

import asyncio
import datetime
import logging
from typing import Optional

from fastapi import HTTPException, status

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

logger = logging.getLogger(__name__)


class ElectionService:
    """Service encapsulating election data aggregation, parsing, and query resolution."""

    def __init__(self):
        self._csu = csu_client
        self._codebooks = codebook_index

    async def initialize(self) -> None:
        """Initializes codebooks on application startup."""
        logger.info("Initializing Election Codebooks Index...")
        self._codebooks.initialize_defaults()
        asyncio.create_task(self._codebooks.load_remote_codebooks())

    async def shutdown(self) -> None:
        """Cleans up HTTP connections on shutdown."""
        logger.info("Shutting down CSU HTTP client...")
        await self._csu.close()

    async def get_overview(self) -> ElectionOverviewResponse:
        """Retrieves high-level summary of ongoing Czech 2026 elections."""
        now_iso = datetime.datetime.now().isoformat()
        senat_xml = await self._csu.get_senat_vysledky()
        senat_res = parse_senate_results(senat_xml)

        kv_cr_xml = await self._csu.get_kv_vysledky_cr()
        kv_summary = parse_kv_cr_overview(kv_cr_xml)

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

    async def get_senate_results(self, obvod: Optional[str | int] = None) -> SenateOverviewResponse:
        """Retrieves Senate results for all 27 contested districts or a specific one."""
        district_num = None
        if obvod is not None:
            district_num = self._codebooks.resolve_senate_district(obvod)
            if district_num is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Senátní obvod '{obvod}' nebyl nalezen. Zadejte číslo obvodu (např. 3) nebo sídlo (např. Cheb).",
                )

        xml_root = await self._csu.get_senat_vysledky()
        return parse_senate_results(xml_root, target_district=district_num)

    async def get_municipal_results(self, obec: str) -> MunicipalResultResponse:
        """Retrieves municipal election results for a given municipality code or name."""
        kod_zastup = self._codebooks.resolve_municipality_code(obec)
        if not kod_zastup:
            search_res = self._codebooks.search(obec, limit=5)
            suggestions = [f"{r.name} (kód: {r.code})" for r in search_res.results]
            detail_msg = f"Obec '{obec}' nebyla nalezena."
            if suggestions:
                detail_msg += f" Možná jste mysleli: {', '.join(suggestions)}"
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail_msg)

        xml_root = await self._csu.get_kv_obec(kod_zastup)
        return parse_municipal_results(xml_root)

    async def search(self, query: str, limit: int = settings.DEFAULT_SEARCH_LIMIT) -> SearchResultResponse:
        """Searches municipalities and Senate districts."""
        return self._codebooks.search(query, limit=limit)

    async def get_progress(self) -> CountingProgressResponse:
        """Calculates counting telemetry and velocity metrics."""
        overview = await self.get_overview()
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


# Global singleton service
election_service = ElectionService()
