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


def test_parse_municipal_results():
    root = ET.fromstring(MOCK_MUNICIPAL_XML)
    res = parse_municipal_results(root)

    assert res.municipality_code == "554782"
    assert res.municipality_name == "Praha hl.m."
    assert res.total_seats == 65
    assert res.is_completed is True
    assert res.turnout.turnout_pct == 50.00
    assert res.winner == "Koalice A"

    # Verify party order
    assert len(res.parties) == 5
    assert res.parties[0].party_name == "Koalice A"
    assert res.parties[0].seats_won == 22
    assert res.parties[1].party_name == "Koalice B"
    assert res.parties[1].seats_won == 18
    assert res.parties[4].seats_won == 0


def test_parse_kv_cr_overview():
    root = ET.fromstring(MOCK_KV_CR_XML)
    summary = parse_kv_cr_overview(root)

    assert summary["precincts_total"] == 14551
    assert summary["precincts_processed"] == 7275
    assert summary["precincts_processed_pct"] == 50.0
    assert len(summary["types"]) == 1
    assert summary["types"][0]["councils_total"] == 6249
