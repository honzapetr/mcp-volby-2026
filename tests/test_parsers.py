"""Unit tests for Senate and Municipal XML parsers."""

import xml.etree.ElementTree as ET
import pytest

from src.parsers.senat_parser import parse_senate_results
from src.parsers.kv_parser import parse_municipal_results, parse_kv_cr_overview


MOCK_SENAT_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY xmlns="http://www.volby.cz/senat/" DATUM_CAS_GENEROVANI="2026-10-10T14:30:00">
  <OBVOD CISLO="3" NAZEV="Cheb">
    <KANDIDAT PORADOVE_CISLO="1" JMENO="Miroslav" PRIJMENI="Plevný" TITULPRED="prof." TITULZA="" HLASY_1KOLO="12500" HLASY_PROC_1KOLO="52.30"/>
    <KANDIDAT PORADOVE_CISLO="2" JMENO="Vladimír" PRIJMENI="Keblíšek" TITULPRED="" TITULZA="" HLASY_1KOLO="8200" HLASY_PROC_1KOLO="34.31"/>
    <KANDIDAT PORADOVE_CISLO="3" JMENO="Pavel" PRIJMENI="Hojda" TITULPRED="Ing." TITULZA="" HLASY_1KOLO="3200" HLASY_PROC_1KOLO="13.39"/>
    <UCAST KOLO="1" OKRSKY_CELKEM="172" OKRSKY_ZPRAC="172" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="85000" VYDANE_OBALKY="24500" UCAST_PROC="28.82" PLATNE_HLASY="23900"/>
  </OBVOD>
  <OBVOD CISLO="6" NAZEV="Louny">
    <KANDIDAT PORADOVE_CISLO="1" JMENO="Jan" PRIJMENI="Novák" TITULPRED="" TITULZA="" HLASY_1KOLO="6000" HLASY_PROC_1KOLO="40.00"/>
    <KANDIDAT PORADOVE_CISLO="2" JMENO="Petr" PRIJMENI="Svoboda" TITULPRED="" TITULZA="" HLASY_1KOLO="5000" HLASY_PROC_1KOLO="33.33"/>
    <KANDIDAT PORADOVE_CISLO="3" JMENO="Eva" PRIJMENI="Dvořáková" TITULPRED="" TITULZA="" HLASY_1KOLO="4000" HLASY_PROC_1KOLO="26.67"/>
    <UCAST KOLO="1" OKRSKY_CELKEM="150" OKRSKY_ZPRAC="150" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="70000" VYDANE_OBALKY="15500" UCAST_PROC="22.14" PLATNE_HLASY="15000"/>
  </OBVOD>
</VYSLEDKY>
"""

MOCK_MUNICIPAL_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T16:00:00">
  <OBEC KODZASTUP="554782" NAZEVZAST="Praha hl.m." OZNAC_TYPU="OBEC" VOLENO_ZASTUP="65" POCET_OBVODU="1" JE_SPOCTENO="1">
    <VYSLEDEK>
      <UCAST OKRSKY_CELKEM="1120" OKRSKY_ZPRAC="1120" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="900000" VYDANE_OBALKY="450000" UCAST_PROC="50.00" VOLICSKE_PRUKAZY="1200" ODEVZDANE_OBALKY="449000" PLATNE_LISTKY="445000" PLATNE_HLASY="28925000"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="1" VSTRANA="101" NAZEV_STRANY="Koalice A" HLASY="8677500" HLASY_PROC="30.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="22" ZASTUPITELE_PROC="33.85"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="2" VSTRANA="102" NAZEV_STRANY="Koalice B" HLASY="7231250" HLASY_PROC="25.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="18" ZASTUPITELE_PROC="27.69"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="3" VSTRANA="103" NAZEV_STRANY="Koalice C" HLASY="5785000" HLASY_PROC="20.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="14" ZASTUPITELE_PROC="21.54"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="4" VSTRANA="104" NAZEV_STRANY="Strana D" HLASY="4338750" HLASY_PROC="15.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="11" ZASTUPITELE_PROC="16.92"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="5" VSTRANA="105" NAZEV_STRANY="Strana E (pod 5%)" HLASY="867750" HLASY_PROC="3.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="0" ZASTUPITELE_PROC="0.00"/>
    </VYSLEDEK>
  </OBEC>
</VYSLEDKY_OBEC>
"""

MOCK_KV_CR_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T15:00:00">
  <TYP_ZASTUP OZNAC_TYPU="OBEC" NAZ_TYPU="Zastupitelstvo obce">
    <UCAST OKRSKY_CELKEM="14551" OKRSKY_ZPRAC="7275" OKRSKY_ZPRAC_PROC="50.00" ZAPSANI_VOLICI="4000000" VYDANE_OBALKY="1800000" UCAST_PROC="45.00"/>
    <ZASTUPIT_INFO ZASTUPITELSTVA_CELKEM="6249" ZASTUPITELSTVA_ZVOLENA="3100" ZASTUPITELE_ZVOLENI="20000"/>
  </TYP_ZASTUP>
</VYSLEDKY>
"""


def test_parse_senate_results_winner_round_1():
    root = ET.fromstring(MOCK_SENAT_XML)
    res = parse_senate_results(root, target_district=3)

    assert len(res.districts) == 1
    d = res.districts[0]
    assert d.district_number == 3
    assert d.district_name == "Cheb"
    assert d.is_completed is True
    assert d.turnout.precincts_processed_pct == 100.0

    # Miroslav Plevný had >50% and must be elected in round 1
    winner = d.candidates[0]
    assert winner.last_name == "Plevný"
    assert winner.votes_pct_round_1 == 52.30
    assert winner.elected_round_1 is True
    assert winner.advances_to_round_2 is False
    assert "Zvolen v 1. kole" in d.status_summary

    # Margins in Round 1
    assert d.lead_margin_votes == 12500 - 8200
    assert d.lead_margin_pct == round(52.30 - 34.31, 2)
    assert d.lead_margin["votes"] == 4300
    assert d.lead_margin["pct"] == 17.99
    assert d.cutoff_margin_votes == 8200 - 3200
    assert d.cutoff_margin_pct == round(34.31 - 13.39, 2)
    assert d.cutoff_margin["votes"] == 5000
    assert d.cutoff_margin["pct"] == 20.92


def test_parse_senate_results_round_2_runoff():
    root = ET.fromstring(MOCK_SENAT_XML)
    res = parse_senate_results(root, target_district=6)

    assert len(res.districts) == 1
    d = res.districts[0]
    assert d.district_number == 6
    assert d.district_name == "Louny"
    assert d.is_completed is True

    # No candidate > 50%, top 2 must advance to round 2
    c1 = d.candidates[0]
    c2 = d.candidates[1]
    assert c1.elected_round_1 is False
    assert c1.advances_to_round_2 is True
    assert c2.advances_to_round_2 is True
    assert d.candidates[2].advances_to_round_2 is False
    assert "Postup do 2. kola" in d.status_summary


MOCK_SENAT_ROUND_2_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY xmlns="http://www.volby.cz/senat/" DATUM_CAS_GENEROVANI="2026-10-17T17:00:00">
  <OBVOD CISLO="6" NAZEV="Louny">
    <KANDIDAT PORADOVE_CISLO="1" JMENO="Jan" PRIJMENI="Novák" TITULPRED="" TITULZA="" HLASY_1KOLO="6000" HLASY_PROC_1KOLO="40.00" HLASY_2KOLO="11500" HLASY_PROC_2KOLO="57.50" ZVOLEN_2KOLO="1"/>
    <KANDIDAT PORADOVE_CISLO="2" JMENO="Petr" PRIJMENI="Svoboda" TITULPRED="" TITULZA="" HLASY_1KOLO="5000" HLASY_PROC_1KOLO="33.33" HLASY_2KOLO="8500" HLASY_PROC_2KOLO="42.50"/>
    <KANDIDAT PORADOVE_CISLO="3" JMENO="Eva" PRIJMENI="Dvořáková" TITULPRED="" TITULZA="" HLASY_1KOLO="4000" HLASY_PROC_1KOLO="26.67"/>
    <UCAST KOLO="1" OKRSKY_CELKEM="150" OKRSKY_ZPRAC="150" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="70000" VYDANE_OBALKY="15500" UCAST_PROC="22.14" PLATNE_HLASY="15000"/>
    <UCAST KOLO="2" OKRSKY_CELKEM="150" OKRSKY_ZPRAC="150" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="70000" VYDANE_OBALKY="20200" UCAST_PROC="28.86" PLATNE_HLASY="20000"/>
  </OBVOD>
</VYSLEDKY>
"""


def test_parse_senate_results_round_2_complete():
    root = ET.fromstring(MOCK_SENAT_ROUND_2_XML)
    registry = {
        (6, 1): {"party_name": "ODS", "nominating_party": "ODS", "political_affiliation": "ODS"},
        (6, 2): {"party_name": "ANO", "nominating_party": "ANO", "political_affiliation": "ANO"},
    }
    res = parse_senate_results(root, target_district=6, candidate_registry=registry)

    assert len(res.districts) == 1
    d = res.districts[0]
    assert d.is_completed is True
    assert d.turnout_round_2 is not None
    assert d.turnout_round_2.turnout_pct == 28.86

    c1 = d.candidates[0]
    c2 = d.candidates[1]
    assert c1.last_name == "Novák"
    assert c1.party_name == "ODS"
    assert c1.votes_round_2 == 11500
    assert c1.votes_pct_round_2 == 57.50
    assert c1.elected_round_2 is True

    assert c2.last_name == "Svoboda"
    assert c2.party_name == "ANO"
    assert c2.votes_round_2 == 8500
    assert c2.votes_pct_round_2 == 42.50

    # Lead margin in round 2
    assert d.lead_margin_votes == 3000
    assert d.lead_margin_pct == 15.00
    assert "Zvolen ve 2. kole: Jan Novák" in d.status_summary


def test_parse_municipal_results():
    root = ET.fromstring(MOCK_MUNICIPAL_XML)
    res = parse_municipal_results(root)

    assert res.municipality_code == "554782"
    assert res.municipality_name == "Praha hl.m."
    assert res.total_seats == 65
    assert res.is_completed is True
    assert res.turnout.turnout_pct == 50.00
    assert res.winner == "Koalice A"
    assert res.leading_party is None
    assert res.majority_seats == 33  # 65 // 2 + 1
    assert res.wasted_votes_pct == 3.00  # Strana E (pod 5%) had 0 seats and 3.00%
    assert res.counting_status == "Sčítání dokončeno"

    # Verify party order
    assert len(res.parties) == 5
    assert res.parties[0].party_name == "Koalice A"
    assert res.parties[0].seats_won == 22
    assert res.parties[1].party_name == "Koalice B"
    assert res.parties[1].seats_won == 18
    assert res.parties[4].seats_won == 0


MOCK_MUNICIPAL_IN_PROGRESS_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T14:45:00">
  <OBEC KODZASTUP="554782" NAZEVZAST="Praha hl.m." OZNAC_TYPU="OBEC" VOLENO_ZASTUP="65" POCET_OBVODU="1" JE_SPOCTENO="0">
    <VYSLEDEK>
      <UCAST OKRSKY_CELKEM="1120" OKRSKY_ZPRAC="560" OKRSKY_ZPRAC_PROC="50.00" ZAPSANI_VOLICI="900000" VYDANE_OBALKY="225000" UCAST_PROC="50.00" PLATNE_HLASY="14000000"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="1" VSTRANA="101" NAZEV_STRANY="Koalice A" HLASY="4200000" HLASY_PROC="30.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="0" ZASTUPITELE_PROC="0.00"/>
      <VOLEBNI_STRANA POR_STR_HLAS_LIST="2" VSTRANA="102" NAZEV_STRANY="Koalice B" HLASY="3500000" HLASY_PROC="25.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="0" ZASTUPITELE_PROC="0.00"/>
    </VYSLEDEK>
  </OBEC>
</VYSLEDKY_OBEC>
"""


def test_parse_municipal_results_in_progress():
    root = ET.fromstring(MOCK_MUNICIPAL_IN_PROGRESS_XML)
    res = parse_municipal_results(root)

    assert res.is_completed is False
    assert res.winner is None  # Winner must be None during counting!
    assert res.leading_party == "Koalice A"  # Leading party must be set during counting!
    assert res.majority_seats == 33
    assert "Probíhá sčítání" in res.counting_status


MOCK_SENATE_BREAKDOWN_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY xmlns="http://www.volby.cz/senat/" DATUM_CAS_GENEROVANI="2026-10-10T15:30:00">
  <OBVOD CISLO="3" NAZEV="Cheb">
    <OBEC KOD="560715" NAZEV="Cheb">
      <UCAST OKRSKY_CELKEM="30" OKRSKY_ZPRAC="30" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="24000" VYDANE_OBALKY="6500" UCAST_PROC="27.08" PLATNE_HLASY="6400"/>
      <KANDIDAT PORADOVE_CISLO="1" JMENO="Miroslav" PRIJMENI="Plevný" HLASY_1KOLO="3500" HLASY_PROC_1KOLO="54.69"/>
      <KANDIDAT PORADOVE_CISLO="2" JMENO="Vladimír" PRIJMENI="Keblíšek" HLASY_1KOLO="2900" HLASY_PROC_1KOLO="45.31"/>
    </OBEC>
    <OBEC KOD="554499" NAZEV="Aš">
      <UCAST OKRSKY_CELKEM="14" OKRSKY_ZPRAC="14" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="9500" VYDANE_OBALKY="2100" UCAST_PROC="22.11" PLATNE_HLASY="2050"/>
      <KANDIDAT PORADOVE_CISLO="1" JMENO="Miroslav" PRIJMENI="Plevný" HLASY_1KOLO="950" HLASY_PROC_1KOLO="46.34"/>
      <KANDIDAT PORADOVE_CISLO="2" JMENO="Vladimír" PRIJMENI="Keblíšek" HLASY_1KOLO="1100" HLASY_PROC_1KOLO="53.66"/>
    </OBEC>
  </OBVOD>
</VYSLEDKY>
"""


def test_parse_senate_district_breakdown():
    from src.parsers.senat_parser import parse_senate_district_breakdown
    root = ET.fromstring(MOCK_SENATE_BREAKDOWN_XML)
    res = parse_senate_district_breakdown(root, district_num=3)

    assert res.district_number == 3
    assert res.municipalities_total == 2
    assert res.municipalities_processed == 2

    # Aš is sorted first alphabetically
    as_res = res.municipalities[0]
    assert as_res.municipality_name == "Aš"
    assert as_res.leader_name == "Vladimír Keblíšek"

    cheb_res = res.municipalities[1]
    assert cheb_res.municipality_name == "Cheb"
    assert cheb_res.leader_name == "Miroslav Plevný"


def test_parse_kv_cr_overview():
    root = ET.fromstring(MOCK_KV_CR_XML)
    summary = parse_kv_cr_overview(root)

    assert summary["precincts_total"] == 14551
    assert summary["precincts_processed"] == 7275
    assert summary["precincts_processed_pct"] == 50.0
    assert len(summary["types"]) == 1
    assert summary["types"][0]["councils_total"] == 6249


@pytest.mark.asyncio
async def test_coalition_scenarios_calculation():
    from unittest.mock import AsyncMock
    from src.services.election_service import ElectionService

    service = ElectionService()
    root = ET.fromstring(MOCK_MUNICIPAL_XML)
    service._csu.get_kv_obec = AsyncMock(return_value=root)

    analysis = await service.get_coalition_scenarios("554782")
    assert analysis.total_seats == 65
    assert analysis.majority_seats == 33
    assert analysis.single_party_majority is None
    assert len(analysis.scenarios) > 0

    # First scenario: Koalice A (22) + Strana D (11) = 33 seats (exact majority, margin 0)
    top_scen = analysis.scenarios[0]
    assert top_scen.is_minimal_winning is True
    assert set(top_scen.parties) == {"Koalice A", "Strana D"}
    assert top_scen.total_seats == 33
    assert top_scen.majority_margin == 0

    # Also verify Koalice A + Koalice B scenario (40 seats, margin 7) exists
    ab_scen = next((s for s in analysis.scenarios if set(s.parties) == {"Koalice A", "Koalice B"}), None)
    assert ab_scen is not None
    assert ab_scen.total_seats == 40
    assert ab_scen.majority_margin == 7
    assert ab_scen.is_minimal_winning is True


@pytest.mark.asyncio
async def test_single_party_majority_scenario():
    from unittest.mock import AsyncMock
    from src.services.election_service import ElectionService

    SINGLE_PARTY_XML = """<?xml version="1.0" encoding="utf-8"?>
    <VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T16:00:00">
      <OBEC KODZASTUP="123456" NAZEVZAST="Malá Lhota" OZNAC_TYPU="OBEC" VOLENO_ZASTUP="9" POCET_OBVODU="1" JE_SPOCTENO="1">
        <VYSLEDEK>
          <UCAST OKRSKY_CELKEM="1" OKRSKY_ZPRAC="1" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="200" VYDANE_OBALKY="150" UCAST_PROC="75.00" PLATNE_HLASY="900"/>
          <VOLEBNI_STRANA POR_STR_HLAS_LIST="1" VSTRANA="1" NAZEV_STRANY="Nezávislí pro Lhotu" HLASY="600" HLASY_PROC="66.67" KANDIDATU_POCET="9" ZASTUPITELE_POCET="6" ZASTUPITELE_PROC="66.67"/>
          <VOLEBNI_STRANA POR_STR_HLAS_LIST="2" VSTRANA="2" NAZEV_STRANY="Hasiči" HLASY="300" HLASY_PROC="33.33" KANDIDATU_POCET="9" ZASTUPITELE_POCET="3" ZASTUPITELE_PROC="33.33"/>
        </VYSLEDEK>
      </OBEC>
    </VYSLEDKY_OBEC>
    """
    service = ElectionService()
    root = ET.fromstring(SINGLE_PARTY_XML)
    service._csu.get_kv_obec = AsyncMock(return_value=root)

    analysis = await service.get_coalition_scenarios("123456")
    assert analysis.total_seats == 9
    assert analysis.majority_seats == 5
    assert analysis.single_party_majority == "Nezávislí pro Lhotu"
    assert any(s.parties == ["Nezávislí pro Lhotu"] for s in analysis.scenarios)
    assert analysis.status_message is not None
    assert "jednobarevnou většinu" in analysis.status_message


def test_wasted_votes_during_counting():
    """Verifies that wasted_votes_pct does not falsely count winning parties during counting."""
    root = ET.fromstring(MOCK_MUNICIPAL_IN_PROGRESS_XML)
    res = parse_municipal_results(root)

    assert res.is_completed is False
    # Koalice A (30%) and Koalice B (25%) are >= 5%, so wasted_votes must be 0.0, not 55.0%
    assert res.wasted_votes_pct == 0.0

    # Add a sub-threshold party (< 5%) to in-progress XML
    XML_WITH_SMALL_PARTY = """<?xml version="1.0" encoding="utf-8"?>
    <VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T14:45:00">
      <OBEC KODZASTUP="554782" NAZEVZAST="Praha hl.m." OZNAC_TYPU="OBEC" VOLENO_ZASTUP="65" POCET_OBVODU="1" JE_SPOCTENO="0">
        <VYSLEDEK>
          <UCAST OKRSKY_CELKEM="100" OKRSKY_ZPRAC="50" OKRSKY_ZPRAC_PROC="50.00" ZAPSANI_VOLICI="10000" VYDANE_OBALKY="5000" UCAST_PROC="50.00" PLATNE_HLASY="50000"/>
          <VOLEBNI_STRANA POR_STR_HLAS_LIST="1" VSTRANA="1" NAZEV_STRANY="Strana A" HLASY="25000" HLASY_PROC="50.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="0" ZASTUPITELE_PROC="0.00"/>
          <VOLEBNI_STRANA POR_STR_HLAS_LIST="2" VSTRANA="2" NAZEV_STRANY="Mikrostrana B" HLASY="1500" HLASY_PROC="3.00" KANDIDATU_POCET="65" ZASTUPITELE_POCET="0" ZASTUPITELE_PROC="0.00"/>
        </VYSLEDEK>
      </OBEC>
    </VYSLEDKY_OBEC>
    """
    res_small = parse_municipal_results(ET.fromstring(XML_WITH_SMALL_PARTY))
    assert res_small.is_completed is False
    assert res_small.wasted_votes_pct == 3.00


def test_senate_district_breakdown_with_candidate_registry():
    """Verifies that parse_senate_district_breakdown enriches candidates with party affiliation from registry."""
    from src.parsers.senat_parser import parse_senate_district_breakdown
    root = ET.fromstring(MOCK_SENATE_BREAKDOWN_XML)
    registry = {
        (3, 1): {
            "first_name": "Miroslav",
            "last_name": "Plevný",
            "party_name": "STAN",
            "nominating_party": "STAN",
            "political_affiliation": "BEZPP",
        },
        (3, 2): {
            "first_name": "Vladimír",
            "last_name": "Keblíšek",
            "party_name": "ANO",
            "nominating_party": "ANO",
            "political_affiliation": "ANO",
        },
    }
    res = parse_senate_district_breakdown(root, district_num=3, candidate_registry=registry)
    assert res.district_number == 3
    assert len(res.municipalities) == 2

    # Check Cheb municipality candidates
    cheb = next(m for m in res.municipalities if m.municipality_name == "Cheb")
    c1 = next(c for c in cheb.candidates if c.candidate_number == 1)
    assert c1.last_name == "Plevný"
    assert c1.party_name == "STAN"
    assert c1.nominating_party == "STAN"
    assert c1.political_affiliation == "BEZPP"


def test_parse_senate_round_2_tie():
    """Verifies handling of an exact vote tie in Round 2."""
    TIE_XML = """<?xml version="1.0" encoding="utf-8"?>
    <VYSLEDKY xmlns="http://www.volby.cz/senat/" DATUM_CAS_GENEROVANI="2026-10-17T18:00:00">
      <OBVOD CISLO="6" NAZEV="Louny">
        <KANDIDAT PORADOVE_CISLO="1" JMENO="Jan" PRIJMENI="Novák" HLASY_1KOLO="6000" HLASY_PROC_1KOLO="40.00" HLASY_2KOLO="10000" HLASY_PROC_2KOLO="50.00"/>
        <KANDIDAT PORADOVE_CISLO="2" JMENO="Petr" PRIJMENI="Svoboda" HLASY_1KOLO="5000" HLASY_PROC_1KOLO="33.33" HLASY_2KOLO="10000" HLASY_PROC_2KOLO="50.00"/>
        <UCAST KOLO="1" OKRSKY_CELKEM="150" OKRSKY_ZPRAC="150" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="70000" VYDANE_OBALKY="15500" UCAST_PROC="22.14" PLATNE_HLASY="15000"/>
        <UCAST KOLO="2" OKRSKY_CELKEM="150" OKRSKY_ZPRAC="150" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="70000" VYDANE_OBALKY="20200" UCAST_PROC="28.86" PLATNE_HLASY="20000"/>
      </OBVOD>
    </VYSLEDKY>
    """
    root = ET.fromstring(TIE_XML)
    res = parse_senate_results(root, target_district=6)
    d = res.districts[0]
    assert d.is_completed is True
    assert d.lead_margin_votes == 0
    assert d.lead_margin_pct == 0.0
    assert "Rovnost hlasů" in d.status_summary
    assert "los" in d.status_summary


def test_parse_senate_round_2_pending():
    """Verifies that a district with Round 2 node but 0 processed precincts is not marked completed."""
    PENDING_XML = """<?xml version="1.0" encoding="utf-8"?>
    <VYSLEDKY xmlns="http://www.volby.cz/senat/" DATUM_CAS_GENEROVANI="2026-10-17T13:50:00">
      <OBVOD CISLO="6" NAZEV="Louny">
        <KANDIDAT PORADOVE_CISLO="1" JMENO="Jan" PRIJMENI="Novák" HLASY_1KOLO="6000" HLASY_PROC_1KOLO="40.00"/>
        <KANDIDAT PORADOVE_CISLO="2" JMENO="Petr" PRIJMENI="Svoboda" HLASY_1KOLO="5000" HLASY_PROC_1KOLO="33.33"/>
        <UCAST KOLO="1" OKRSKY_CELKEM="150" OKRSKY_ZPRAC="150" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="70000" VYDANE_OBALKY="15500" UCAST_PROC="22.14" PLATNE_HLASY="15000"/>
        <UCAST KOLO="2" OKRSKY_CELKEM="150" OKRSKY_ZPRAC="0" OKRSKY_ZPRAC_PROC="0.00" ZAPSANI_VOLICI="70000" VYDANE_OBALKY="0" UCAST_PROC="0.00" PLATNE_HLASY="0"/>
      </OBVOD>
    </VYSLEDKY>
    """
    root = ET.fromstring(PENDING_XML)
    res = parse_senate_results(root, target_district=6)
    d = res.districts[0]
    assert d.is_completed is False
    assert "sčítání ještě nezačalo" in d.status_summary


def test_parse_municipal_results_with_candidates():
    """Verifies parsing of municipal XML containing candidates and elected representatives."""
    MUNICIPAL_CANDIDATES_XML = """<?xml version="1.0" encoding="utf-8"?>
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
    root = ET.fromstring(MUNICIPAL_CANDIDATES_XML)
    res = parse_municipal_results(root)

    assert res.municipality_code == "554782"
    assert res.is_completed is True

    # Check party 1 candidates
    p1 = res.parties[0]
    assert p1.party_name == "Koalice Modrá"
    assert len(p1.candidates) == 3
    assert len(p1.elected_candidates) == 2

    c1 = p1.candidates[0]
    assert c1.first_name == "Martin"
    assert c1.last_name == "Dvořák"
    assert c1.votes == 3500
    assert c1.is_elected is True
    assert c1.mandate_status == "Zvolen"
    assert c1.order_elected == 1

    c3 = p1.candidates[2]
    assert c3.first_name == "Tomáš"
    assert c3.last_name == "Černý"
    assert c3.votes == 2300
    assert c3.is_elected is False
    assert c3.mandate_status == "Náhradník"

    # Check top-level elected council members (across all parties)
    assert len(res.elected_representatives) == 3
    names_elected = [f"{c.first_name} {c.last_name}" for c in res.elected_representatives]
    assert "Martin Dvořák" in names_elected
    assert "Klára Veselá" in names_elected
    assert "Lenka Králová" in names_elected


def test_parse_municipal_results_with_candidate_registry():
    """Verifies that candidate names are matched from candidate registry if missing in XML."""
    XML_WITHOUT_NAMES = """<?xml version="1.0" encoding="utf-8"?>
    <VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T17:00:00">
      <OBEC KODZASTUP="554782" NAZEVZAST="Praha hl.m." OZNAC_TYPU="OBEC" VOLENO_ZASTUP="1" POCET_OBVODU="1" JE_SPOCTENO="1">
        <VYSLEDEK>
          <UCAST OKRSKY_CELKEM="10" OKRSKY_ZPRAC="10" OKRSKY_ZPRAC_PROC="100.00" ZAPSANI_VOLICI="10000" VYDANE_OBALKY="5000" UCAST_PROC="50.00" PLATNE_HLASY="5000"/>
          <VOLEBNI_STRANA POR_STR_HLAS_LIST="1" VSTRANA="101" NAZEV_STRANY="Lokální sdružení" HLASY="5000" HLASY_PROC="100.00" KANDIDATU_POCET="1" ZASTUPITELE_POCET="1" ZASTUPITELE_PROC="100.00">
            <ZASTUPITEL PORADOVE_CISLO="1" HLASY="5000" HLASY_PROC="100.00" PORADI_ZVOLENI="1" MANDAT="A"/>
          </VOLEBNI_STRANA>
        </VYSLEDEK>
      </OBEC>
    </VYSLEDKY_OBEC>
    """
    registry = {
        ("554782", 101, 1): {
            "first_name": "Alena",
            "last_name": "Nováková",
            "title_pre": "Ing.",
            "title_post": "",
            "party_name": "Lokální sdružení",
            "nominating_party": "Lokální sdružení",
            "political_affiliation": "BEZPP",
        }
    }
    root = ET.fromstring(XML_WITHOUT_NAMES)
    res = parse_municipal_results(root, candidate_registry=registry)

    assert len(res.elected_representatives) == 1
    elected = res.elected_representatives[0]
    assert elected.candidate_number == 1
    assert elected.first_name == "Alena"
    assert elected.last_name == "Nováková"
    assert elected.title_pre == "Ing."
    assert elected.is_elected is True
    assert elected.votes == 5000
