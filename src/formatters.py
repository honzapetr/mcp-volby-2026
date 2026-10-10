"""Data projection and formatting module for Czech Elections 2026 MCP Server.

Provides modular, token-efficient projection and formatting of election responses:
- Projecting relevant fields and levels of detail (summary, parties, elected, full)
- Accent-insensitive filtering and dynamic sorting
- Serializing to optimized, compact JSON (excluding nulls) or highly legible Markdown
"""

from enum import Enum
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from src.config import settings
from src.models import (
    CoalitionAnalysisResponse,
    CountingProgressResponse,
    ElectionOverviewResponse,
    MunicipalPartyResult,
    MunicipalResultResponse,
    PrecinctSpeedResponse,
    SearchResultResponse,
    SenateDistrictBreakdownResponse,
    SenateDistrictResult,
    SenateOverviewResponse,
)
from src.parsers.codebook_loader import normalize_text

logger = logging.getLogger(__name__)


class DetailLevel(str, Enum):
    """Granularity level for municipal and Senate results."""
    SUMMARY = "summary"
    PARTIES = "parties"
    ELECTED = "elected"
    FULL = "full"
    AUTO = "auto"


class ResponseFormat(str, Enum):
    """Output serialization format."""
    JSON = "json"
    MARKDOWN = "markdown"


class SenateStatusFilter(str, Enum):
    """Filter for Senate election districts."""
    ALL = "all"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    CLOSE_RACES = "close_races"


class BreakdownSortBy(str, Enum):
    """Sorting criterion for Senate breakdown municipalities."""
    VOTERS = "voters"
    TURNOUT = "turnout"
    PROCESSED = "processed"
    NAME = "name"


def project_municipal_results(
    result: MunicipalResultResponse,
    detail_level: str = settings.DEFAULT_MUNICIPAL_DETAIL,
    include_candidates: bool = False,
    party_filter: Optional[str] = None,
    top_parties: Optional[int] = None,
) -> MunicipalResultResponse:
    """Projects municipal election results to a compact, token-efficient representation.

    Args:
        result: Full municipal result response.
        detail_level: Level of detail ('summary', 'parties', 'elected', 'full').
        include_candidates: If True, candidate lists for all parties are kept.
        party_filter: If provided, candidate list is only preserved for the matching party.
        top_parties: Maximum number of parties to return (ordered by votes).

    Returns:
        Projected MunicipalResultResponse without unnecessary candidate bloat.
    """
    res = result.model_copy(deep=True)
    lvl = detail_level.lower() if detail_level else DetailLevel.PARTIES.value

    # 1. Truncate parties if top_parties is specified
    if top_parties is not None and top_parties > 0:
        res.parties = res.parties[:top_parties]

    normalized_party_filter = normalize_text(party_filter) if party_filter else None

    # 2. Filter candidates based on level of detail
    if lvl == DetailLevel.SUMMARY.value:
        res.parties = [
            p.model_copy(update={"candidates": [], "elected_candidates": []})
            for p in res.parties
        ]
        res.elected_representatives = []

    elif lvl == DetailLevel.FULL.value or include_candidates:
        # Full representation: retain all candidates and elected representatives
        pass

    else:
        # 'parties' (default) or 'elected'
        projected_parties: List[MunicipalPartyResult] = []
        for p in res.parties:
            matches_party = False
            if normalized_party_filter:
                p_norm = normalize_text(p.party_name)
                matches_party = (
                    normalized_party_filter in p_norm
                    or str(p.party_id) == party_filter
                    or str(p.list_number) == party_filter
                )

            if matches_party:
                # User specifically asked for this party's candidates
                projected_parties.append(p)
            else:
                # Omit large candidate array, keep party metrics
                projected_parties.append(
                    p.model_copy(update={"candidates": [], "elected_candidates": []})
                )

        res.parties = projected_parties

        if lvl == DetailLevel.PARTIES.value and not res.is_completed and not any(p.seats_won > 0 for p in res.parties):
            # During counting when no seats are allocated yet, keep elected_representatives empty
            res.elected_representatives = []

    return res


def project_senate_results(
    result: SenateOverviewResponse,
    detail_level: str = settings.DEFAULT_SENATE_DETAIL,
    status_filter: Optional[str] = None,
) -> SenateOverviewResponse:
    """Projects Senate election results to eliminate candidate payload bloat.

    Args:
        result: Full Senate overview response.
        detail_level: 'auto', 'summary', or 'full'.
        status_filter: 'all', 'completed', 'in_progress', or 'close_races'.

    Returns:
        Projected SenateOverviewResponse.
    """
    res = result.model_copy(deep=True)
    lvl = detail_level.lower() if detail_level else DetailLevel.AUTO.value
    filt = status_filter.lower() if status_filter else SenateStatusFilter.ALL.value

    # 1. Apply status filter
    filtered_districts: List[SenateDistrictResult] = []
    for d in res.districts:
        if filt == SenateStatusFilter.COMPLETED.value:
            if d.is_completed:
                filtered_districts.append(d)
        elif filt == SenateStatusFilter.IN_PROGRESS.value:
            if not d.is_completed and d.turnout.precincts_processed > 0:
                filtered_districts.append(d)
        elif filt == SenateStatusFilter.CLOSE_RACES.value:
            is_close = (
                d.turnout.precincts_processed > 0
                and (
                    (d.cutoff_margin_pct is not None and d.cutoff_margin_pct <= 5.0)
                    or (d.lead_margin_pct is not None and d.lead_margin_pct <= 5.0)
                )
            )
            if is_close:
                filtered_districts.append(d)
        else:
            filtered_districts.append(d)

    res.districts = filtered_districts

    # 2. Project candidates per district
    # If viewing all districts (multi-district query) and auto/summary is requested:
    # retain only top 2 candidates (the leader and runner-up/elected)
    is_multi_district = len(res.districts) > 1
    should_summarize = (lvl == DetailLevel.SUMMARY.value) or (lvl == DetailLevel.AUTO.value and is_multi_district)

    if should_summarize:
        projected_districts: List[SenateDistrictResult] = []
        for d in res.districts:
            projected_districts.append(
                d.model_copy(update={"candidates": d.candidates[:2]})
            )
        res.districts = projected_districts

    return res


def project_senate_district_breakdown(
    result: SenateDistrictBreakdownResponse,
    limit: Optional[int] = settings.DEFAULT_BREAKDOWN_LIMIT,
    obec_filter: Optional[str] = None,
    sort_by: str = BreakdownSortBy.VOTERS.value,
    summary_only: bool = False,
) -> SenateDistrictBreakdownResponse:
    """Projects Senate breakdown results across municipalities within a district.

    Args:
        result: Full Senate district breakdown response.
        limit: Maximum number of municipalities to return (0 or None for all).
        obec_filter: Name or code of specific municipality to search.
        sort_by: Sorting criterion ('voters', 'turnout', 'processed', 'name').
        summary_only: If True, returns only aggregated summary statistics without municipality list.

    Returns:
        Projected SenateDistrictBreakdownResponse with summary statistics.
    """
    res = result.model_copy(deep=True)
    mun_list = list(res.municipalities)

    # 1. Compute aggregate summary
    if mun_list:
        voters_with_data = [m for m in mun_list if m.turnout.registered_voters > 0]
        highest_turnout_m = max(voters_with_data, key=lambda m: m.turnout.turnout_pct, default=None)
        lowest_turnout_m = min(voters_with_data, key=lambda m: m.turnout.turnout_pct, default=None)
        largest_m = max(mun_list, key=lambda m: m.turnout.registered_voters, default=None)

        res.summary = {
            "municipalities_total": res.municipalities_total,
            "municipalities_processed": res.municipalities_processed,
            "processed_pct": round(
                (res.municipalities_processed / res.municipalities_total * 100), 2
            ) if res.municipalities_total > 0 else 0.0,
            "largest_municipality": (
                {"name": largest_m.municipality_name, "voters": largest_m.turnout.registered_voters}
                if largest_m else None
            ),
            "highest_turnout": (
                {"name": highest_turnout_m.municipality_name, "turnout_pct": highest_turnout_m.turnout.turnout_pct}
                if highest_turnout_m else None
            ),
            "lowest_turnout": (
                {"name": lowest_turnout_m.municipality_name, "turnout_pct": lowest_turnout_m.turnout.turnout_pct}
                if lowest_turnout_m else None
            ),
        }

    # 2. Filter by specific municipality if requested
    if obec_filter:
        norm_filter = normalize_text(obec_filter)
        res.municipalities = [
            m for m in mun_list
            if norm_filter in normalize_text(m.municipality_name) or str(m.municipality_code) == str(obec_filter)
        ]
        return res

    if summary_only:
        res.municipalities = []
        return res

    # 3. Sort municipalities
    sort_key = sort_by.lower() if sort_by else BreakdownSortBy.VOTERS.value
    if sort_key == BreakdownSortBy.TURNOUT.value:
        mun_list.sort(key=lambda m: m.turnout.turnout_pct, reverse=True)
    elif sort_key == BreakdownSortBy.PROCESSED.value:
        mun_list.sort(key=lambda m: m.turnout.precincts_processed_pct, reverse=True)
    elif sort_key == BreakdownSortBy.NAME.value:
        mun_list.sort(key=lambda m: m.municipality_name)
    else:  # Default: 'voters'
        mun_list.sort(key=lambda m: m.turnout.registered_voters, reverse=True)

    # 4. Apply limit
    if limit is not None and limit > 0:
        res.municipalities = mun_list[:limit]
    else:
        res.municipalities = mun_list

    return res


def format_to_markdown(data: BaseModel) -> str:
    """Formats any election Pydantic model into clean, token-efficient Markdown tables."""
    lines: List[str] = []

    if isinstance(data, MunicipalResultResponse):
        lines.append(f"## Výsledky komunálních voleb 2026: {data.municipality_name} (kód: {data.municipality_code})")
        lines.append(
            f"**Stav:** {data.counting_status or 'N/A'} | "
            f"**Sečteno:** {data.turnout.precincts_processed}/{data.turnout.precincts_total} okrsků ({data.turnout.precincts_processed_pct:.1f} %) | "
            f"**Účast:** {data.turnout.turnout_pct:.2f} %"
        )
        lines.append(
            f"**Zastupitelů:** {data.total_seats} | "
            f"**Potřebná většina:** {data.majority_seats} mandátů | "
            f"**Propadlé hlasy:** {data.wasted_votes_pct:.2f} %"
        )
        if data.winner:
            lines.append(f"**Vítěz:** {data.winner}")
        elif data.leading_party:
            lines.append(f"**Průběžně vede:** {data.leading_party}")

        lines.append("")
        lines.append("### Výsledky kandidujících stran")
        lines.append("| Číslo | Strana | Hlasy | Hlasy % | Mandáty | Mandáty % |")
        lines.append("|:---:|:---|---:|---:|---:|---:|")
        for p in data.parties:
            lines.append(
                f"| {p.list_number} | {p.party_name} | {p.votes:,} | {p.votes_pct:.2f} % | {p.seats_won} | {p.seats_pct:.1f} % |"
            )

        if data.elected_representatives:
            lines.append("")
            lines.append(f"### Zvolení zastupitelé ({len(data.elected_representatives)})")
            lines.append("| Poř. | Jméno a příjmení | Volební strana | Polit. příslušnost | Věk | Povolání | Přednostní hlasy |")
            lines.append("|:---:|:---|:---|:---|:---:|:---|---:|")
            for idx, c in enumerate(data.elected_representatives, start=1):
                name = f"{c.title_pre} {c.first_name} {c.last_name} {c.title_post}".strip()
                party = c.party_name or "N/A"
                affil = c.political_affiliation or "BezPP"
                age = str(c.age) if c.age is not None else "-"
                occ = c.occupation or "-"
                lines.append(f"| {idx} | {name} | {party} | {affil} | {age} | {occ} | {c.votes:,} |")

    elif isinstance(data, SenateOverviewResponse):
        lines.append(f"## {data.election_title}")
        lines.append(f"**Sečteno obvodů:** {data.districts_completed} z {data.districts_total} | **Čas dat:** {data.generated_at}")
        lines.append("")

        if len(data.districts) == 1:
            d = data.districts[0]
            lines.append(f"### Obvod č. {d.district_number} - {d.district_name}")
            lines.append(
                f"**Stav:** {d.status_summary} | "
                f"**Sečteno:** {d.turnout.precincts_processed}/{d.turnout.precincts_total} okrsků ({d.turnout.precincts_processed_pct:.1f} %) | "
                f"**Účast:** {d.turnout.turnout_pct:.2f} %"
            )
            if d.turnout_round_2 and d.turnout_round_2.precincts_processed > 0:
                lines.append(
                    f"**2. kolo účast:** {d.turnout_round_2.turnout_pct:.2f} % "
                    f"({d.turnout_round_2.precincts_processed}/{d.turnout_round_2.precincts_total} okrsků)"
                )
            lines.append("")
            lines.append("| Číslo | Kandidát | Strana / Příslušnost | 1. kolo hlasy | 1. kolo % | 2. kolo % | Status |")
            lines.append("|:---:|:---|:---|---:|---:|---:|:---|")
            for c in d.candidates:
                name = f"{c.title_pre} {c.first_name} {c.last_name} {c.title_post}".strip()
                party = c.party_name or c.nominating_party or "-"
                r2_pct = f"{c.votes_pct_round_2:.2f} %" if c.votes_pct_round_2 is not None else "-"
                status = "Zvolen (1. kolo)" if c.elected_round_1 else (
                    "Zvolen (2. kolo)" if c.elected_round_2 else (
                        "Postupuje do 2. kola" if c.advances_to_round_2 else "-"
                    )
                )
                lines.append(f"| {c.candidate_number} | {name} | {party} | {c.votes_round_1:,} | {c.votes_pct_round_1:.2f} % | {r2_pct} | {status} |")

        else:
            lines.append("| Obvod | Sídlo | Sečteno | Lídr / Vítěz | % 1.kolo | 2. kandidát | % 1.kolo | Náskok |")
            lines.append("|:---:|:---|:---:|:---|---:|:---|---:|:---|")
            for d in data.districts:
                c1 = d.candidates[0] if len(d.candidates) > 0 else None
                c2 = d.candidates[1] if len(d.candidates) > 1 else None
                c1_str = f"{c1.first_name} {c1.last_name}" if c1 else "-"
                c1_pct = f"{c1.votes_pct_round_1:.1f} %" if c1 else "-"
                c2_str = f"{c2.first_name} {c2.last_name}" if c2 else "-"
                c2_pct = f"{c2.votes_pct_round_1:.1f} %" if c2 else "-"
                margin = f"{d.lead_margin_pct:+.1f} p.b." if d.lead_margin_pct is not None else "-"
                proc = f"{d.turnout.precincts_processed_pct:.0f} %"
                lines.append(f"| {d.district_number} | {d.district_name} | {proc} | {c1_str} | {c1_pct} | {c2_str} | {c2_pct} | {margin} |")

    elif isinstance(data, SenateDistrictBreakdownResponse):
        lines.append(f"## Senátní obvod č. {data.district_number} - {data.district_name}: Rozpad po obcích")
        lines.append(f"**Sečteno obcí:** {data.municipalities_processed} / {data.municipalities_total} | **Čas dat:** {data.generated_at}")
        if data.summary:
            lines.append(
                f"**Souhrn:** Zpracováno {data.summary.get('processed_pct', 0)} % obcí. "
                f"Největší obec: {data.summary.get('largest_municipality', {}).get('name', 'N/A')} "
                f"({data.summary.get('largest_municipality', {}).get('voters', 0):,} voličů)."
            )
        lines.append("")
        lines.append("| Kód | Obec | Okrsky | Účast | Zapsaní voliči | Vedoucí kandidát |")
        lines.append("|:---:|:---|:---:|---:|---:|:---|")
        for m in data.municipalities:
            t = m.turnout
            leader = m.leader_name or (m.candidates[0].last_name if m.candidates else "-")
            lines.append(f"| {m.municipality_code} | {m.municipality_name} | {t.precincts_processed}/{t.precincts_total} | {t.turnout_pct:.1f} % | {t.registered_voters:,} | {leader} |")

    elif isinstance(data, CoalitionAnalysisResponse):
        lines.append(f"## Koaliční analýza: {data.municipality_name} (kód: {data.municipality_code})")
        lines.append(f"**Zastupitelů:** {data.total_seats} | **Většina:** {data.majority_seats} mandátů")
        if data.status_message:
            lines.append(f"**Stav:** {data.status_message}")
        lines.append("")
        if data.scenarios:
            lines.append("### Většinové koaliční scénáře (seřazeno dle stability)")
            lines.append("| Poř. | Složení koalice | Počet stran | Mandáty celkem | Převis nad většinu | Minimální vítězná (MWC)? |")
            lines.append("|:---:|:---|:---:|---:|---:|:---:|")
            for idx, s in enumerate(data.scenarios, start=1):
                parties_str = " + ".join(s.parties)
                mwc_str = "ANO" if s.is_minimal_winning else "Ne"
                lines.append(f"| {idx} | {parties_str} | {s.parties_count} | {s.total_seats} ({s.seats_pct:.1f} %) | +{s.majority_margin} | {mwc_str} |")

    elif isinstance(data, PrecinctSpeedResponse):
        order_str = "Nejpomalejší" if data.order == "slowest" else "Nejrychlejší"
        lines.append(f"## Rychlost sčítání okrsků ({data.election_type.upper()}) - {order_str} komise")
        lines.append(f"**Filtr:** {data.filter_applied or 'Celá ČR'} | **Celkem nalezeno:** {data.total_precincts_found}")
        lines.append(f"**Shrnutí:** {data.summary_message}")
        lines.append("")
        lines.append("| Okrsek | Obec | Čas odevzdání | Pořadí ČSÚ | Účast % | Vydané obálky | Platné hlasy |")
        lines.append("|:---:|:---|:---:|---:|---:|---:|---:|")
        for p in data.precincts:
            time_part = p.processed_at.split("T")[-1] if "T" in p.processed_at else p.processed_at
            lines.append(f"| {p.precinct_number} | {p.municipality_name or p.municipality_code} | {time_part} | #{p.processing_order} | {p.turnout_pct:.1f} % | {p.issued_envelopes:,} | {p.valid_votes:,} |")

    elif isinstance(data, CountingProgressResponse):
        lines.append("## Průběžné tempo sčítání hlasů (Telemetrie)")
        lines.append(f"**Stav:** {data.status_message}")
        lines.append(f"- **Senát PČR:** {data.senate_pct:.1f} % sečtených okrsků")
        lines.append(f"- **Obecní zastupitelstva:** {data.municipal_pct:.1f} % sečtených okrsků")
        lines.append(f"- **Sčítání aktivní:** {'Ano' if data.counting_active else 'Ne'}")

    elif isinstance(data, ElectionOverviewResponse):
        lines.append("## Souhrnný přehled voleb ČR 2026")
        lines.append(f"**Sčítání zahájeno:** {'Ano' if data.counting_started else 'Ne'} | **Poslední aktualizace:** {data.last_updated}")
        lines.append("")
        lines.append(f"### Senát ČR")
        lines.append(f"- Sečteno obvodů: {data.senate_summary.get('districts_completed', 0)} / {data.senate_summary.get('districts_total', 0)}")
        lines.append(f"- Sečteno okrsků: {data.senate_summary.get('precincts_processed', 0):,} / {data.senate_summary.get('precincts_total', 0):,} ({data.senate_summary.get('precincts_processed_pct', 0.0):.1f} %)")
        lines.append("")
        lines.append(f"### Zastupitelstva obcí")
        lines.append(f"- Sečteno okrsků: {data.municipal_summary.get('precincts_processed', 0):,} / {data.municipal_summary.get('precincts_total', 0):,} ({data.municipal_summary.get('precincts_processed_pct', 0.0):.1f} %)")

    elif isinstance(data, SearchResultResponse):
        lines.append(f"## Výsledky vyhledávání pro: '{data.query}'")
        lines.append(f"**Nalezeno záznamů:** {data.total_found}")
        lines.append("")
        lines.append("| Typ | Kód / Číslo | Název | Upřesnění |")
        lines.append("|:---:|:---:|:---|:---|")
        for item in data.results:
            typ = "Senát" if item.item_type == "senat" else "Obec"
            lines.append(f"| {typ} | {item.code} | {item.name} | {item.description} |")

    else:
        # Fallback to compact JSON
        lines.append(data.model_dump_json(exclude_none=True, indent=2))

    return "\n".join(lines)


def format_response_payload(data: BaseModel, format_type: str = settings.DEFAULT_RESPONSE_FORMAT) -> str:
    """Serializes response data model to either compact JSON (excluding nulls) or Markdown.

    Args:
        data: Pydantic response model.
        format_type: 'json' or 'markdown'.

    Returns:
        Formatted string for MCP text content or API response.
    """
    fmt = format_type.lower() if format_type else ResponseFormat.JSON.value
    if fmt == ResponseFormat.MARKDOWN.value:
        return format_to_markdown(data)
    # Exclude None to reduce token usage and omit empty/null fields
    return data.model_dump_json(exclude_none=True, indent=2)
