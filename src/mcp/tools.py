"""MCP Tools registration and execution handlers."""

import logging
from typing import List

from fastapi import HTTPException
from mcp.server import Server
from mcp.types import TextContent, Tool

from src.config import settings
from src.services.election_service import election_service

logger = logging.getLogger(__name__)

# MCP Server instance
mcp_server = Server(settings.MCP_SERVER_NAME)


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
                "Vrací volební účast, počet volených zastupitelů, % sečtených okrsků, výsledky kandidujících stran včetně mandátů, "
                "a jmenný seznam zvolených zastupitelů i kandidátů včetně jejich přednostních hlasů (křížků)."
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
                        "description": f"Maximální počet výsledků (výchozí {settings.DEFAULT_SEARCH_LIMIT}).",
                        "default": settings.DEFAULT_SEARCH_LIMIT,
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
        Tool(
            name="get_senate_district_breakdown",
            description=(
                "Získá detailní rozpad výsledků voleb do Senátu 2026 po jednotlivých obcích v daném senátním obvodu. "
                "Umožňuje analyzovat geografické rozdíly v podpoře kandidátů mezi městy a obcemi uvnitř obvodu. "
                "Parametr 'obvod': číslo obvodu (např. 3) nebo název sídla (např. 'Cheb', 'Praha 5')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "obvod": {
                        "type": ["string", "integer"],
                        "description": "Číslo senátního obvodu (např. 3) nebo název sídla (např. 'Cheb').",
                    }
                },
                "required": ["obvod"],
            },
        ),
        Tool(
            name="get_coalition_scenarios",
            description=(
                "Vypočítá možné povolební většinové koaliční scénáře pro zastupitelstvo dané obce či města. "
                "Identifikuje minimální vítězné koalice (Minimal Winning Coalitions - MWC, kde žádná strana není přebytečná), "
                "případnou jednobarevnou většinu a potřebný počet mandátů k většině (total_seats // 2 + 1). "
                "Parametr 'obec': název obce (např. 'Praha', 'Brno') nebo 6místný kód obce ČSÚ (např. '554782')."
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
                },
            },
        ),
    ]


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handles tool invocations from MCP clients."""
    try:
        if name == "get_election_overview":
            res = await election_service.get_overview()
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_senate_results":
            obvod = arguments.get("obvod")
            res = await election_service.get_senate_results(obvod)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_municipal_results":
            obec = arguments.get("obec")
            if not obec:
                return [TextContent(type="text", text="Chyba: Chybí povinný parametr 'obec'.")]
            res = await election_service.get_municipal_results(obec)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "search_municipality_or_district":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", settings.DEFAULT_SEARCH_LIMIT))
            res = await election_service.search(query, limit)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_live_counting_progress":
            res = await election_service.get_progress()
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_senate_district_breakdown":
            obvod = arguments.get("obvod")
            if obvod is None:
                return [TextContent(type="text", text="Chyba: Chybí povinný parametr 'obvod'.")]
            res = await election_service.get_senate_district_breakdown(obvod)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        elif name == "get_coalition_scenarios":
            obec = arguments.get("obec")
            if not obec:
                return [TextContent(type="text", text="Chyba: Chybí povinný parametr 'obec'.")]
            res = await election_service.get_coalition_scenarios(obec)
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

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
            return [TextContent(type="text", text=res.model_dump_json(indent=2))]

        else:
            return [TextContent(type="text", text=f"Chyba: Neznámý nástroj '{name}'.")]

    except HTTPException as exc:
        return [TextContent(type="text", text=f"Chyba: {exc.detail}")]
    except Exception as exc:
        logger.exception("Chyba při volání nástroje %s: %s", name, exc)
        return [TextContent(type="text", text=f"Interní chyba při zpracování požadavku: {exc}")]

