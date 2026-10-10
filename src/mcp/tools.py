"""MCP Tools registration and execution handlers."""

import logging
from typing import List, Optional

from fastapi import HTTPException
from mcp.server import Server
from mcp.types import TextContent, Tool

from src.config import settings
from src.formatters import (
    BreakdownSortBy,
    DetailLevel,
    ResponseFormat,
    SenateStatusFilter,
    format_response_payload,
)
from src.services.election_service import election_service

logger = logging.getLogger(__name__)

# MCP Server instance
mcp_server = Server(settings.MCP_SERVER_NAME)


@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Exposes all tools to MCP clients with rich parameterization and projection options."""
    return [
        Tool(
            name="get_election_overview",
            description=(
                "Získá celkový přehled o stavu voleb v ČR 2026 (Senát a obecní zastupitelstva). "
                "Vrací, zda již začalo sčítání (sobota po 14:00), celkovou účast a procento sečtených okrsků."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown' (přehledný text pro LLM).",
                    }
                },
            },
        ),
        Tool(
            name="get_senate_results",
            description=(
                "Získá výsledky voleb do Senátu Parlamentu ČR 2026 (1. kolo, obměna 27 obvodů). "
                "Parametr 'obvod' je volitelný: číslo obvodu (např. 3) nebo název sídla (např. 'Cheb', 'Praha 5', 'Brno'). "
                "Při dotazu na celou ČR vrací souhrn lídrů bez zahlcení kontextu, detailní kandidáty lze vyžádat pro obvod."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "obvod": {
                        "type": ["string", "integer"],
                        "description": "Číslo senátního obvodu (např. 3) nebo název sídla (např. 'Cheb', 'Praha 5').",
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": [DetailLevel.AUTO.value, DetailLevel.SUMMARY.value, DetailLevel.FULL.value],
                        "default": DetailLevel.AUTO.value,
                        "description": (
                            "Úroveň detailu: 'auto' (souhrn lídrů pro více obvodů, plný detail pro 1 obvod), "
                            "'summary' (pouze lídři a náskoky), 'full' (všichni kandidáti)."
                        ),
                    },
                    "status_filter": {
                        "type": "string",
                        "enum": [
                            SenateStatusFilter.ALL.value,
                            SenateStatusFilter.COMPLETED.value,
                            SenateStatusFilter.IN_PROGRESS.value,
                            SenateStatusFilter.CLOSE_RACES.value,
                        ],
                        "default": SenateStatusFilter.ALL.value,
                        "description": (
                            "Volitelný filtr obvodů: 'all' (všechny), 'completed' (dokončené), "
                            "'in_progress' (probíhající sčítání), 'close_races' (těsné souboje s marží pod 5%)."
                        ),
                    },
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown'.",
                    },
                },
            },
        ),
        Tool(
            name="get_municipal_results",
            description=(
                "Získá výsledky voleb do zastupitelstva konkrétní obce nebo města (komunální volby 2026). "
                "Uveďte název obce (např. 'Praha', 'Brno', 'Ostrava', 'Plzeň') nebo šestimístný kód obce ČSÚ (např. '554782'). "
                "Ve výchozím stavu vrací výsledky stran a zvolené zastupitele (bez stovek nezvolených kandidátů pro úsporu tokenů). "
                "Pro zobrazení kandidátů konkrétní strany použijte parametr 'party'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "obec": {
                        "type": "string",
                        "description": "Název obce (např. 'Praha', 'Brno') nebo 6místný kód obce ČSÚ (např. '554782').",
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": [
                            DetailLevel.PARTIES.value,
                            DetailLevel.SUMMARY.value,
                            DetailLevel.ELECTED.value,
                            DetailLevel.FULL.value,
                        ],
                        "default": DetailLevel.PARTIES.value,
                        "description": (
                            "Úroveň detailu: 'parties' (výsledky stran + zvolení zastupitelé - výchozí a doporučeno), "
                            "'summary' (pouze účast, mandáty stran a propadlé hlasy), "
                            "'elected' (pouze zvolení zastupitelé), "
                            "'full' (kompletní kandidátní listiny všech kandidátů)."
                        ),
                    },
                    "include_candidates": {
                        "type": "boolean",
                        "default": False,
                        "description": "Pokud True, vrátí kompletní seznamy všech nezvolených kandidátů všech stran.",
                    },
                    "party": {
                        "type": "string",
                        "description": "Volitelné: název, číslo nebo ID konkrétní strany pro zobrazení její kandidátní listiny.",
                    },
                    "top_parties": {
                        "type": "integer",
                        "description": "Volitelné: omezení na N nejsilnějších stran dle počtu hlasů.",
                    },
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown'.",
                    },
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
                        "description": f"Maximální počet výsledků (výchozí {settings.DEFAULT_SEARCH_LIMIT}).",
                        "default": settings.DEFAULT_SEARCH_LIMIT,
                    },
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown'.",
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
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown'.",
                    }
                },
            },
        ),
        Tool(
            name="get_senate_district_breakdown",
            description=(
                "Získá detailní rozpad výsledků voleb do Senátu 2026 po jednotlivých obcích v daném senátním obvodu. "
                "Umožňuje analyzovat geografické rozdíly v podpoře kandidátů mezi městy a obcemi uvnitř obvodu. "
                "Standardně vrací 10 nejvýznamnějších obcí obvodu s agregovaným statistickým souhrnem."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "obvod": {
                        "type": ["string", "integer"],
                        "description": "Číslo senátního obvodu (např. 3) nebo název sídla (např. 'Cheb').",
                    },
                    "limit": {
                        "type": "integer",
                        "default": settings.DEFAULT_BREAKDOWN_LIMIT,
                        "description": f"Maximální počet obcí k zobrazení (výchozí {settings.DEFAULT_BREAKDOWN_LIMIT}, 0 pro všechny).",
                    },
                    "obec": {
                        "type": "string",
                        "description": "Volitelné: vyhledání a zobrazení konkrétní obce uvnitř senátního obvodu.",
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": [
                            BreakdownSortBy.VOTERS.value,
                            BreakdownSortBy.TURNOUT.value,
                            BreakdownSortBy.PROCESSED.value,
                            BreakdownSortBy.NAME.value,
                        ],
                        "default": BreakdownSortBy.VOTERS.value,
                        "description": "Kritérium řazení obcí: 'voters' (největší obce), 'turnout' (účast), 'name' (abecedně).",
                    },
                    "summary_only": {
                        "type": "boolean",
                        "default": False,
                        "description": "Pokud True, vrátí pouze statistický přehled obvodu bez dlouhého seznamu jednotlivých obcí.",
                    },
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown'.",
                    },
                },
                "required": ["obvod"],
            },
        ),
        Tool(
            name="get_coalition_scenarios",
            description=(
                "Vypočítá možné povolební většinové koaliční scénáře pro zastupitelstvo dané obce či města. "
                "Identifikuje minimální vítězné koalice (Minimal Winning Coalitions - MWC, kde žádná strana není přebytečná), "
                "případnou jednobarevnou většinu a potřebný počet mandátů k většině (total_seats // 2 + 1)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "obec": {
                        "type": "string",
                        "description": "Název obce (např. 'Praha', 'Brno') nebo 6místný kód obce ČSÚ (např. '554782').",
                    },
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown'.",
                    },
                },
                "required": ["obec"],
            },
        ),
        Tool(
            name="get_precinct_counting_speed",
            description=(
                "Získá časy odevzdání a zpracování spočtených hlasů z volebních okrsků (v kolik hodin komise odevzdala hlasy "
                "a ČSÚ schválil zápis). Umožňuje identifikovat nejpomalejší i nejrychlejší volební komise v ČR, v konkrétní "
                "obci (např. 'Praha') nebo v senátním obvodu, případně zjistit čas zpracování konkrétního okrsku."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "election_type": {
                        "type": "string",
                        "description": "Typ voleb: 'obce' (komunální volby, výchozí) nebo 'senat' (volby do Senátu).",
                        "enum": ["obce", "senat"],
                        "default": "obce",
                    },
                    "order": {
                        "type": "string",
                        "description": "Řazení výsledků: 'slowest' (nejpomalejší komise jako první, výchozí) nebo 'fastest' (nejrychlejší komise jako první).",
                        "enum": ["slowest", "fastest"],
                        "default": "slowest",
                    },
                    "obec": {
                        "type": "string",
                        "description": "Volitelné: název obce (např. 'Praha', 'Brno') nebo 6místný kód obce ČSÚ pro filtraci okrsků dané obce.",
                    },
                    "obvod": {
                        "type": ["string", "integer"],
                        "description": "Volitelné: číslo senátního obvodu (např. 3) nebo sídlo (např. 'Cheb') pro filtraci okrsků daného obvodu.",
                    },
                    "okrsek": {
                        "type": "integer",
                        "description": "Volitelné: konkrétní číslo volebního okrsku pro zjištění času jeho zpracování.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximální počet vrácených okrsků (výchozí 10, maximum 100).",
                        "default": 10,
                    },
                    "format": {
                        "type": "string",
                        "enum": [ResponseFormat.JSON.value, ResponseFormat.MARKDOWN.value],
                        "default": ResponseFormat.JSON.value,
                        "description": "Formát výstupu: 'json' (výchozí) nebo 'markdown'.",
                    },
                },
            },
        ),
    ]


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handles tool invocations from MCP clients with optimized serialization."""
    try:
        format_type = str(arguments.get("format", settings.DEFAULT_RESPONSE_FORMAT))

        if name == "get_election_overview":
            res = await election_service.get_overview()
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        elif name == "get_senate_results":
            obvod = arguments.get("obvod")
            detail_level = str(arguments.get("detail_level", settings.DEFAULT_SENATE_DETAIL))
            status_filter = arguments.get("status_filter")
            res = await election_service.get_senate_results(
                obvod=obvod,
                detail_level=detail_level,
                status_filter=status_filter,
            )
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        elif name == "get_municipal_results":
            obec = arguments.get("obec")
            if not obec:
                return [TextContent(type="text", text="Chyba: Chybí povinný parametr 'obec'.")]
            detail_level = str(arguments.get("detail_level", settings.DEFAULT_MUNICIPAL_DETAIL))
            include_candidates = bool(arguments.get("include_candidates", False))
            party = arguments.get("party")
            top_parties = arguments.get("top_parties")
            top_parties_int = int(top_parties) if top_parties is not None else None

            res = await election_service.get_municipal_results(
                obec=obec,
                detail_level=detail_level,
                include_candidates=include_candidates,
                party=party,
                top_parties=top_parties_int,
            )
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        elif name == "search_municipality_or_district":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", settings.DEFAULT_SEARCH_LIMIT))
            res = await election_service.search(query, limit)
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        elif name == "get_live_counting_progress":
            res = await election_service.get_progress()
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        elif name == "get_senate_district_breakdown":
            obvod = arguments.get("obvod")
            if obvod is None:
                return [TextContent(type="text", text="Chyba: Chybí povinný parametr 'obvod'.")]
            limit = int(arguments.get("limit", settings.DEFAULT_BREAKDOWN_LIMIT))
            obec_filter = arguments.get("obec")
            sort_by = str(arguments.get("sort_by", BreakdownSortBy.VOTERS.value))
            summary_only = bool(arguments.get("summary_only", False))

            res = await election_service.get_senate_district_breakdown(
                obvod=obvod,
                limit=limit,
                obec=obec_filter,
                sort_by=sort_by,
                summary_only=summary_only,
            )
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        elif name == "get_coalition_scenarios":
            obec = arguments.get("obec")
            if not obec:
                return [TextContent(type="text", text="Chyba: Chybí povinný parametr 'obec'.")]
            res = await election_service.get_coalition_scenarios(obec)
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        elif name == "get_precinct_counting_speed":
            election_type = arguments.get("election_type", "obce")
            order = arguments.get("order", "slowest")
            obec = arguments.get("obec")
            obvod = arguments.get("obvod")
            okrsek = arguments.get("okrsek")
            limit = int(arguments.get("limit", 10))
            res = await election_service.get_precinct_speed(
                election_type=election_type,
                order=order,
                obec=obec,
                obvod=obvod,
                okrsek=okrsek,
                limit=limit,
            )
            return [TextContent(type="text", text=format_response_payload(res, format_type))]

        else:
            return [TextContent(type="text", text=f"Chyba: Neznámý nástroj '{name}'.")]

    except HTTPException as exc:
        return [TextContent(type="text", text=f"Chyba: {exc.detail}")]
    except Exception as exc:
        logger.exception("Chyba při volání nástroje %s: %s", name, exc)
        return [TextContent(type="text", text=f"Interní chyba při zpracování požadavku: {exc}")]
