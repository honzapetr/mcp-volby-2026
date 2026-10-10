"""Unit and integration tests for data projection, formatting, and token-saving MCP options."""

import xml.etree.ElementTree as ET
import pytest

from src.formatters import (
    BreakdownSortBy,
    DetailLevel,
    ResponseFormat,
    SenateStatusFilter,
    format_response_payload,
    format_to_markdown,
    project_municipal_results,
    project_senate_district_breakdown,
    project_senate_results,
)
from src.mcp.tools import handle_call_tool, handle_list_tools
from src.parsers.kv_parser import parse_municipal_results
from src.parsers.senat_parser import parse_senate_district_breakdown, parse_senate_results
from tests.test_parsers import (
    MOCK_SENAT_XML,
    MOCK_SENATE_BREAKDOWN_XML,
)

MOCK_MUNICIPAL_CANDIDATES_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T17:00:00">
  <OBEC KODZASTUP="554782" NAZEVZAST="Praha hl.m." OZNAC_TYPU="OBEC" VOLENO_ZASTUP="3" POCET_OBVODU="1" JE_SPOCTENO="1">
    <VYSLEDEK>
      <UCAST OKRSKY_CELKEM="10" OKRSKY_ZPRAC="10" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="10000" VYDANE_OBALKY="5000" UCAST_PROC="50.00" PLATNE_HLASY="15000"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="1" VSTRANA="101" NAZEV_STRANY="Koalice Modrá" HLASY="9000" HLASY_PROC="60.00" KANDIDATU_POCET="3" ZASTUPITELE_POCET="2" ZASTUPITELE_PROC="66.67">
        <ZASTUPITEL PORADOVE_CISLO="1" JMENO="Martin" PRIJMENI="Dvořák" TITULPRED="Ing." TITULZA="" HLASY="3500" HLASY_PROC="38.89" PORADI_ZVOLENI="1" MANDAT="A"/>
        <ZASTUPITEL PORADOVE_CISLO="2" JMENO="Klára" PRIJMENI="Veselá" TITULPRED="MUDr." TITULZA="" HLASY="3200" HLASY_PROC="35.56" PORADI_ZVOLENI="2" MANDAT="A"/>
        <KANDIDAT PORADOVE_CISLO="3" JMENO="Tomáš" PRIJMENI="Černý" TITULPRED="" TITULZA="" HLASY="2300" HLASY_PROC="25.56" MANDAT="N" ZVOLEN="0"/>
      </VOLEBNI_STRANA>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="2" VSTRANA="102" NAZEV_STRANY="Hnutí Zelené" HLASY="6000" HLASY_PROC="40.00" KANDIDATU_POCET="2" ZASTUPITELE_POCET="1" ZASTUPITELE_PROC="33.33">
        <ZASTUPITEL PORADOVE_CISLO="1" JMENO="Lenka" PRIJMENI="Králová" TITULPRED="Mgr." TITULZA="Ph.D." HLASY="4000" HLASY_PROC="66.67" PORADI_ZVOLENI="1" MANDAT="A"/>
        <KANDIDAT PORADOVE_CISLO="2" JMENO="Jakub" PRIJMENI="Moravec" TITULPRED="" TITULZA="" HLASY="2000" HLASY_PROC="33.33" MANDAT="N" ZVOLEN="0"/>
      </VOLEBNI_STRANA>
    </VYSLEDEK>
  </OBEC>
</VYSLEDKY_OBEC>
"""


def test_project_municipal_results_parties_omits_candidates():
    root = ET.fromstring(MOCK_MUNICIPAL_CANDIDATES_XML)
    raw = parse_municipal_results(root)

    # In raw, each party has candidates
    assert len(raw.parties[0].candidates) == 3
    assert len(raw.parties[1].candidates) == 2
    assert len(raw.elected_representatives) == 3

    # Projected: detail_level="parties" prunes candidates arrays in parties
    projected = project_municipal_results(raw, detail_level="parties", include_candidates=False)

    assert projected.municipality_name == "Praha hl.m."
    assert len(projected.parties) == 2
    # Candidate lists inside parties must be empty to avoid context bloat
    for p in projected.parties:
        assert len(p.candidates) == 0
        assert len(p.elected_candidates) == 0

    # Elected representatives list is preserved
    assert len(projected.elected_representatives) == 3


def test_project_municipal_results_summary():
    root = ET.fromstring(MOCK_MUNICIPAL_CANDIDATES_XML)
    raw = parse_municipal_results(root)

    projected = project_municipal_results(raw, detail_level="summary")

    assert projected.total_seats == 3
    assert projected.majority_seats == 2
    assert len(projected.elected_representatives) == 0
    for p in projected.parties:
        assert len(p.candidates) == 0


def test_project_municipal_results_party_filter():
    root = ET.fromstring(MOCK_MUNICIPAL_CANDIDATES_XML)
    raw = parse_municipal_results(root)

    # Filter specifically for "Koalice Modrá"
    projected = project_municipal_results(
        raw,
        detail_level="parties",
        party_filter="Koalice Modrá",
    )

    p_a = next(p for p in projected.parties if p.party_name == "Koalice Modrá")
    # For Koalice Modrá, candidates should be preserved
    assert len(p_a.candidates) == 3

    # For other parties, candidates should be omitted
    p_b = next(p for p in projected.parties if p.party_name == "Hnutí Zelené")
    assert len(p_b.candidates) == 0


def test_project_municipal_results_top_parties():
    root = ET.fromstring(MOCK_MUNICIPAL_CANDIDATES_XML)
    raw = parse_municipal_results(root)

    projected = project_municipal_results(raw, top_parties=1)
    assert len(projected.parties) == 1
    assert projected.parties[0].party_name == "Koalice Modrá"


def test_project_senate_results_auto_multi_district():
    root = ET.fromstring(MOCK_SENAT_XML)
    raw = parse_senate_results(root)

    # In MOCK_SENAT_XML there are 2 districts (3 and 6)
    assert len(raw.districts) == 2

    # In "auto" or "summary" mode for multiple districts, each district should only retain top 2 candidates
    projected = project_senate_results(raw, detail_level="auto")
    for d in projected.districts:
        assert len(d.candidates) <= 2


def test_project_senate_results_status_filter():
    root = ET.fromstring(MOCK_SENAT_XML)
    raw = parse_senate_results(root)

    completed_proj = project_senate_results(raw, status_filter="completed")
    assert all(d.is_completed for d in completed_proj.districts)


def test_project_senate_district_breakdown():
    root = ET.fromstring(MOCK_SENATE_BREAKDOWN_XML)
    raw = parse_senate_district_breakdown(root, district_num=3)

    # Breakdown has 2 municipalities in mock
    projected = project_senate_district_breakdown(raw, limit=1)
    assert len(projected.municipalities) == 1
    assert projected.summary is not None
    assert "largest_municipality" in projected.summary

    # Summary only
    sum_proj = project_senate_district_breakdown(raw, summary_only=True)
    assert len(sum_proj.municipalities) == 0
    assert sum_proj.summary is not None


def test_format_payload_json_and_markdown():
    root = ET.fromstring(MOCK_MUNICIPAL_CANDIDATES_XML)
    raw = parse_municipal_results(root)
    projected = project_municipal_results(raw, detail_level="parties")

    # JSON serialization must exclude nulls
    json_out = format_response_payload(projected, format_type="json")
    assert '"votes_round_2"' not in json_out
    assert '"Praha hl.m."' in json_out

    # Markdown serialization
    md_out = format_response_payload(projected, format_type="markdown")
    assert "## Výsledky komunálních voleb" in md_out
    assert "| Koalice Modrá |" in md_out


@pytest.mark.asyncio
async def test_mcp_tool_with_markdown_and_parameters():
    # Call municipal results with format="markdown"
    res_md = await handle_call_tool(
        "get_municipal_results",
        {"obec": "Praha", "detail_level": "parties", "format": "markdown"},
    )
    assert len(res_md) == 1
    assert "## Výsledky komunálních voleb" in res_md[0].text

    # Call senate results with format="markdown"
    res_sen = await handle_call_tool(
        "get_senate_results",
        {"obvod": 3, "format": "markdown"},
    )
    assert len(res_sen) == 1
    assert "## Volby do Senátu" in res_sen[0].text
