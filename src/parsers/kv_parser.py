"""Parser for Municipal elections (volby do zastupitelstev obcí) XML data."""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from src.models import (
    MunicipalPartyResult,
    MunicipalResultResponse,
    TurnoutInfo,
)

logger = logging.getLogger(__name__)


def _strip_ns(tag: str) -> str:
    """Removes XML namespace prefix if present."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_municipal_results(root: ET.Element) -> MunicipalResultResponse:
    """Parses vysledky_obec_XXXXXX.xml for a specific town or city council."""
    generated_at = root.attrib.get("DATUM_CAS_GENEROVANI", "")

    # Find the OBEC element
    obec_elem = None
    for child in root.iter():
        if _strip_ns(child.tag) == "OBEC":
            obec_elem = child
            break

    if obec_elem is None:
        raise ValueError("V XML souboru nebyl nalezen prvek OBEC.")

    kod_zastup = obec_elem.attrib.get("KODZASTUP", "")
    nazev_zast = obec_elem.attrib.get("NAZEVZAST", "")
    oznac_typu = obec_elem.attrib.get("OZNAC_TYPU", "OBEC")
    voleno_zastup = int(obec_elem.attrib.get("VOLENO_ZASTUP", 0))
    je_spocteno = (obec_elem.attrib.get("JE_SPOCTENO", "0") == "1")

    # Extract turnout
    turnout = TurnoutInfo(
        precincts_total=0,
        precincts_processed=0,
        precincts_processed_pct=0.0,
        registered_voters=0,
        issued_envelopes=0,
        turnout_pct=0.0,
        valid_votes=0,
    )

    parties: List[MunicipalPartyResult] = []

    for child in obec_elem.iter():
        tag = _strip_ns(child.tag)
        if tag == "UCAST":
            turnout = TurnoutInfo(
                precincts_total=int(child.attrib.get("OKRSKY_CELKEM", 0)),
                precincts_processed=int(child.attrib.get("OKRSKY_ZPRAC", 0)),
                precincts_processed_pct=float(child.attrib.get("OKRSKY_ZPRAC_PROC", 0.0)),
                registered_voters=int(child.attrib.get("ZAPSANI_VOLICI", 0)),
                issued_envelopes=int(child.attrib.get("VYDANE_OBALKY", 0)),
                turnout_pct=float(child.attrib.get("UCAST_PROC", 0.0)),
                valid_votes=int(child.attrib.get("PLATNE_HLASY", 0)),
            )
        elif tag == "VOLEBNI_STRANA":
            party = MunicipalPartyResult(
                list_number=int(child.attrib.get("POR_STR_HLAS_LIST", 0)),
                party_id=int(child.attrib.get("VSTRANA", 0)),
                party_name=child.attrib.get("NAZEV_STRANY", ""),
                votes=int(child.attrib.get("HLASY", 0)),
                votes_pct=float(child.attrib.get("HLASY_PROC", 0.0)),
                seats_won=int(child.attrib.get("ZASTUPITELE_POCET", 0)),
                seats_pct=float(child.attrib.get("ZASTUPITELE_PROC", 0.0)),
                candidates_count=int(child.attrib.get("KANDIDATU_POCET", 0)),
            )
            parties.append(party)

    # Sort parties: by votes descending, then seats won, then list number
    parties.sort(key=lambda p: (p.votes, p.seats_won, -p.list_number), reverse=True)

    winner = parties[0].party_name if (parties and parties[0].votes > 0) else None

    # Check completeness
    is_completed = je_spocteno or (
        turnout.precincts_processed == turnout.precincts_total and turnout.precincts_total > 0
    )

    return MunicipalResultResponse(
        municipality_code=kod_zastup,
        municipality_name=nazev_zast,
        council_type=oznac_typu,
        total_seats=voleno_zastup,
        is_completed=is_completed,
        generated_at=generated_at,
        turnout=turnout,
        parties=parties,
        winner=winner,
    )


def parse_kv_cr_overview(root: ET.Element) -> Dict[str, any]:
    """Parses nationwide municipal results overview (vysledky.xml)."""
    generated_at = root.attrib.get("DATUM_CAS_GENEROVANI", "")
    typy = []
    total_precincts = 0
    processed_precincts = 0

    for child in root:
        if _strip_ns(child.tag) != "TYP_ZASTUP":
            continue

        oznac = child.attrib.get("OZNAC_TYPU", "")
        nazev = child.attrib.get("NAZ_TYPU", "")
        ucast_elem = None
        zastup_elem = None

        for sub in child:
            sub_tag = _strip_ns(sub.tag)
            if sub_tag == "UCAST":
                ucast_elem = sub
            elif sub_tag == "ZASTUPIT_INFO":
                zastup_elem = sub

        ptotal = int(ucast_elem.attrib.get("OKRSKY_CELKEM", 0)) if ucast_elem is not None else 0
        pproc = int(ucast_elem.attrib.get("OKRSKY_ZPRAC", 0)) if ucast_elem is not None else 0
        total_precincts += ptotal
        processed_precincts += pproc

        typy.append({
            "type_code": oznac,
            "type_name": nazev,
            "precincts_total": ptotal,
            "precincts_processed": pproc,
            "precincts_pct": float(ucast_elem.attrib.get("OKRSKY_ZPRAC_PROC", 0.0)) if ucast_elem is not None else 0.0,
            "turnout_pct": float(ucast_elem.attrib.get("UCAST_PROC", 0.0)) if ucast_elem is not None else 0.0,
            "councils_total": int(zastup_elem.attrib.get("ZASTUPITELSTVA_CELKEM", 0)) if zastup_elem is not None else 0,
            "councils_elected": int(zastup_elem.attrib.get("ZASTUPITELSTVA_ZVOLENA", 0)) if zastup_elem is not None else 0,
        })

    pct_overall = round((processed_precincts / total_precincts * 100), 2) if total_precincts > 0 else 0.0

    return {
        "generated_at": generated_at,
        "precincts_total": total_precincts,
        "precincts_processed": processed_precincts,
        "precincts_processed_pct": pct_overall,
        "types": typy,
    }
