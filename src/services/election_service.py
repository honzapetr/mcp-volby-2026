"""Election Service: Centralized business logic for processing Czech 2026 election data."""

import asyncio
import datetime
import logging
import itertools
from typing import List, Optional

from fastapi import HTTPException, status

from src.client_csu import csu_client
from src.config import settings
from src.models import (
    CoalitionAnalysisResponse,
    CoalitionScenario,
    CountingProgressResponse,
    ElectionOverviewResponse,
    MunicipalResultResponse,
    PrecinctSpeedResponse,
    PrecinctTimingResult,
    SearchResultResponse,
    SenateDistrictBreakdownResponse,
    SenateOverviewResponse,
)
from src.parsers.codebook_loader import codebook_index
from src.parsers.kv_parser import parse_kv_cr_overview, parse_municipal_results
from src.parsers.precinct_parser import parse_precinct_batch
from src.parsers.senat_parser import parse_senate_district_breakdown, parse_senate_results

logger = logging.getLogger(__name__)


class ElectionService:
    """Service encapsulating election data aggregation, parsing, and query resolution."""

    def __init__(self):
        self._csu = csu_client
        self._codebooks = codebook_index
        self._precinct_registry: dict = {}

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

        def _get_district_active_turnout(d):
            if d.turnout_round_2 is not None and (
                d.turnout_round_2.precincts_processed > 0
                or (d.turnout.precincts_processed == d.turnout.precincts_total and not any(c.elected_round_1 for c in d.candidates))
            ):
                return d.turnout_round_2
            return d.turnout

        senat_precincts_total = sum(_get_district_active_turnout(d).precincts_total for d in senat_res.districts)
        senat_precincts_proc = sum(_get_district_active_turnout(d).precincts_processed for d in senat_res.districts)
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
                    detail=(
                        f"Senátní obvod '{obvod}' nebyl nalezen. "
                        "V roce 2026 se volí pouze 27 senátních obvodů (č. 3, 6, 9, ... 81). "
                        "Zadejte číslo voleného obvodu (např. 3) nebo sídlo (např. Cheb)."
                    ),
                )

        xml_root = await self._csu.get_senat_vysledky()
        res = parse_senate_results(xml_root, target_district=district_num)
        if district_num is not None and not res.districts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pro senátní obvod č. {district_num} nejsou v datech ČSÚ k dispozici žádné výsledky.",
            )
        return res

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

    async def get_senate_district_breakdown(self, obvod: str | int) -> SenateDistrictBreakdownResponse:
        """Retrieves votes across all municipalities within a specific Senate district."""
        district_num = self._codebooks.resolve_senate_district(obvod)
        if district_num is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Senátní obvod '{obvod}' nebyl nalezen. Zadejte číslo obvodu (např. 3) nebo sídlo (např. Cheb).",
            )

        district_name = self._codebooks.senate_districts.get(district_num)
        name_str = district_name.name if district_name else f"Obvod č. {district_num}"

        xml_root = await self._csu.get_senat_obvod_obce(district_num)
        return parse_senate_district_breakdown(xml_root, district_num, district_name=name_str)

    async def get_coalition_scenarios(self, municipality: str) -> CoalitionAnalysisResponse:
        """Calculates minimal winning coalitions and majority scenarios for a municipal council."""
        municipal_res = await self.get_municipal_results(municipality)

        total_seats = municipal_res.total_seats
        majority_seats = municipal_res.majority_seats or (total_seats // 2 + 1 if total_seats > 0 else 0)

        # Filter parties with at least 1 seat
        qualifying_parties = [p for p in municipal_res.parties if p.seats_won > 0]

        single_party_majority: Optional[str] = None
        for p in qualifying_parties:
            if p.seats_won >= majority_seats:
                single_party_majority = p.party_name
                break

        scenarios: List[CoalitionScenario] = []

        if majority_seats > 0 and qualifying_parties:
            n = len(qualifying_parties)
            # Bound combination depth if number of parties is large to avoid combinatorial explosion
            max_r = min(n, 5 if n > 8 else n)

            # If there is a single-party majority, only that entity forms the minimal winning coalition
            if single_party_majority:
                sp_p = next(p for p in qualifying_parties if p.party_name == single_party_majority)
                scenarios.append(
                    CoalitionScenario(
                        parties=[single_party_majority],
                        total_seats=sp_p.seats_won,
                        seats_pct=round((sp_p.seats_won / total_seats * 100), 2) if total_seats > 0 else 0.0,
                        majority_margin=sp_p.seats_won - majority_seats,
                        parties_count=1,
                        is_minimal_winning=True,
                    )
                )
            else:
                for r in range(2, max_r + 1):
                    for combo in itertools.combinations(qualifying_parties, r):
                        combo_seats = sum(p.seats_won for p in combo)
                        if combo_seats >= majority_seats:
                            # Minimal Winning Coalition: NO member can leave without losing majority
                            is_mwc = all((combo_seats - p.seats_won) < majority_seats for p in combo)

                            if is_mwc or r <= 3:
                                party_names = [p.party_name for p in combo]
                                seats_pct = round((combo_seats / total_seats * 100), 2) if total_seats > 0 else 0.0
                                margin = combo_seats - majority_seats

                                scenarios.append(
                                    CoalitionScenario(
                                        parties=party_names,
                                        total_seats=combo_seats,
                                        seats_pct=seats_pct,
                                        majority_margin=margin,
                                        parties_count=len(party_names),
                                        is_minimal_winning=is_mwc,
                                    )
                                )

                # Sort scenarios:
                # 1. Minimal winning first
                # 2. Fewer parties first (simpler coalitions are more stable)
                # 3. Smallest excess margin (closer to minimum required majority)
                scenarios.sort(
                    key=lambda s: (
                        not s.is_minimal_winning,
                        s.parties_count,
                        s.majority_margin,
                    )
                )

        status_msg: Optional[str] = None
        if not municipal_res.is_completed and not qualifying_parties:
            status_msg = (
                f"Sčítání v obci '{municipal_res.municipality_name}' probíhá "
                f"({municipal_res.turnout.precincts_processed}/{municipal_res.turnout.precincts_total} okrsků). "
                "Mandáty se přidělují až po 100% sečtení všech okrsků."
            )
        elif single_party_majority:
            sp_p = next(p for p in qualifying_parties if p.party_name == single_party_majority)
            status_msg = (
                f"Strana '{single_party_majority}' získala jednobarevnou většinu "
                f"({sp_p.seats_won} z {total_seats} mandátů). Koalice není nutná."
            )
        elif scenarios:
            mwc_count = sum(1 for s in scenarios if s.is_minimal_winning)
            status_msg = (
                f"Pro většinu {majority_seats} z {total_seats} mandátů nalezeno "
                f"{mwc_count} minimálních vítězných koalic (MWC) a celkem {len(scenarios)} scénářů."
            )
        elif not qualifying_parties:
            status_msg = "Žádná strana nezískala mandáty."
        else:
            status_msg = f"Nebyly nalezeny žádné většinové koalice pro {majority_seats} mandátů."

        return CoalitionAnalysisResponse(
            municipality_code=municipal_res.municipality_code,
            municipality_name=municipal_res.municipality_name,
            total_seats=total_seats,
            majority_seats=majority_seats,
            is_completed=municipal_res.is_completed,
            single_party_majority=single_party_majority,
            scenarios=scenarios[:25],
            status_message=status_msg,
        )

    async def get_precinct_speed(
        self,
        election_type: str = "obce",
        order: str = "slowest",
        obec: Optional[str | int] = None,
        obvod: Optional[str | int] = None,
        okrsek: Optional[int] = None,
        limit: int = 10,
    ) -> PrecinctSpeedResponse:
        """Returns precinct submission and counting timing metrics, slowest/fastest commissions."""
        election_type_norm = "senat" if "senat" in str(election_type).lower() else "obce"
        order_norm = "fastest" if str(order).lower() in ("fastest", "nejrychlejsi", "fast", "rychle") else "slowest"
        limit_bounded = max(1, min(limit, 100))

        # Map known municipality names
        muni_map = {kod: item.name for kod, item in self._codebooks.municipalities.items()}

        # Fetch latest batch from CSU (gracefully handled if unavailable yet)
        batch_generated_at = ""
        try:
            if election_type_norm == "senat":
                xml_root = await self._csu.get_senat_okrsky()
            else:
                xml_root = await self._csu.get_kv_okrsky()
            batch_generated_at, batch_precincts = parse_precinct_batch(
                xml_root, election_type=election_type_norm, municipality_names=muni_map
            )
            for p in batch_precincts:
                reg_key = (election_type_norm, p.municipality_code, p.precinct_number)
                if reg_key not in self._precinct_registry or p.processing_order >= self._precinct_registry[reg_key].processing_order:
                    self._precinct_registry[reg_key] = p
        except Exception as exc:
            logger.warning("Could not fetch okrsky batch from CSU for %s: %s", election_type_norm, exc)

        # Filter registry by election type
        matching_precincts = [
            p for (etype, _, _), p in self._precinct_registry.items()
            if etype == election_type_norm
        ]

        # Apply municipality name backfill if missing
        for p in matching_precincts:
            if not p.municipality_name and p.municipality_code in muni_map:
                p.municipality_name = muni_map[p.municipality_code]

        filter_parts = []

        # Filter by municipality if requested
        if obec is not None:
            kod = self._codebooks.resolve_municipality_code(obec)
            if not kod:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Obec '{obec}' nebyla nalezena v číselníku.",
                )
            muni_name = muni_map.get(kod, str(obec))
            matching_precincts = [p for p in matching_precincts if p.municipality_code == kod]
            filter_parts.append(f"Obec: {muni_name} ({kod})")

        # Filter by Senate district if requested
        if obvod is not None:
            dist_num = self._codebooks.resolve_senate_district(obvod)
            if dist_num is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Senátní obvod '{obvod}' nebyl nalezen.",
                )
            dist_obj = self._codebooks.senate_districts.get(dist_num)
            dist_name = dist_obj.name if dist_obj else f"Obvod č. {dist_num}"
            matching_precincts = [p for p in matching_precincts if p.district_number == dist_num]
            filter_parts.append(f"Senátní obvod: č. {dist_num} ({dist_name})")

        # Filter by precinct number if requested
        if okrsek is not None:
            try:
                okrsek_int = int(okrsek)
                matching_precincts = [p for p in matching_precincts if p.precinct_number == okrsek_int]
                filter_parts.append(f"Okrsek č. {okrsek_int}")
            except (ValueError, TypeError):
                pass

        filter_applied = ", ".join(filter_parts) if filter_parts else "Celá ČR"

        # Sort precincts by processed_at timestamp
        reverse_sort = (order_norm == "slowest")
        matching_precincts.sort(key=lambda p: (p.processed_at or "", p.processing_order), reverse=reverse_sort)

        total_found = len(matching_precincts)
        selected_precincts = matching_precincts[:limit_bounded]

        # Construct analytical summary message
        if not selected_precincts:
            summary_msg = (
                f"Pro zadaná kritéria ({filter_applied}) nebyly nalezeny žádné zpracované okrsky. "
                "Data sčítání pro tyto okrsky prozatím nemusí být v otevřených datech ČSÚ zpracována."
            )
        else:
            lead = selected_precincts[0]
            lead_muni = lead.municipality_name or f"kód {lead.municipality_code}"
            lead_time = lead.processed_at.split("T")[-1] if "T" in lead.processed_at else (lead.processed_at or "neznámý čas")
            speed_label = "Nejpomalejší" if order_norm == "slowest" else "Nejrychlejší"
            summary_msg = (
                f"{speed_label} evidovaná komise ({filter_applied}): okrsek č. {lead.precinct_number} "
                f"v obci {lead_muni} — čas zpracování {lead_time} "
                f"(volební účast {lead.turnout_pct:.1f} %, odevzdáno {lead.issued_envelopes} obálek)."
            )

        return PrecinctSpeedResponse(
            election_type=election_type_norm,
            order=order_norm,
            filter_applied=filter_applied,
            total_precincts_found=total_found,
            generated_at=batch_generated_at or datetime.datetime.now().isoformat(),
            precincts=selected_precincts,
            summary_message=summary_msg,
        )


# Global singleton service
election_service = ElectionService()

