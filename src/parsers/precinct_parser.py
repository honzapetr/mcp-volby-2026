"""Parser for precinct-level results and submission timings (vysledky_okrsky.xml).

Parses incremental batch XML files from CSU open data (kv_vysledky_okrsky.xsd and se_vysledky_okrsky.xsd).
Extracts official validation timestamps (DATUM_CAS_ZPRAC), turnout, and handles repeated/corrected
submissions (PORADI_ZPRAC).
"""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from src.models import PrecinctTimingResult

logger = logging.getLogger(__name__)


def _strip_ns(tag: str) -> str:
    """Removes XML namespace prefix if present."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_precinct_batch(
    root: ET.Element,
    election_type: str = "obce",
    municipality_names: Optional[Dict[str, str]] = None,
) -> Tuple[str, List[PrecinctTimingResult]]:
    """Parses a vysledky_okrsky.xml batch document into PrecinctTimingResult objects.

    Args:
        root: The XML root element (<VYSLEDKY_OKRSKY>).
        election_type: 'obce' or 'senat'.
        municipality_names: Optional mapping from 6-digit municipality code to municipality name.

    Returns:
        Tuple of (generated_at timestamp, list of PrecinctTimingResult objects).
    """
    generated_at = root.attrib.get("DATUM_CAS_GENEROVANI", "")
    precincts_by_key: Dict[Tuple[str, int], PrecinctTimingResult] = {}

    for elem in root.iter():
        if _strip_ns(elem.tag) != "OKRSEK":
            continue

        attribs = elem.attrib

        # Extract municipality code (CIS_OBEC or KODZASTUP)
        raw_obec = attribs.get("CIS_OBEC") or attribs.get("KODZASTUP", "")
        if not raw_obec:
            continue
        municipality_code = str(raw_obec).strip().zfill(6)

        # Extract precinct number (CIS_OKRSEK)
        try:
            precinct_number = int(attribs.get("CIS_OKRSEK", 0))
        except (ValueError, TypeError):
            continue

        if precinct_number <= 0:
            continue

        # Extract Senate district number if applicable
        raw_obvod = attribs.get("CIS_OBVOD")
        district_number = int(raw_obvod) if raw_obvod is not None and raw_obvod.isdigit() else None

        # Extract processing order and timestamp
        try:
            processing_order = int(attribs.get("PORADI_ZPRAC", 1))
        except (ValueError, TypeError):
            processing_order = 1

        processed_at = attribs.get("DATUM_CAS_ZPRAC", "")

        # Extract repeated flag
        opakovane_raw = attribs.get("OPAKOVANE", "0").strip().lower()
        is_repeated = opakovane_raw in ("1", "true")

        # Extract turnout details from child <UCAST_OKRSEK>
        registered_voters = 0
        issued_envelopes = 0
        valid_votes = 0
        turnout_pct = 0.0

        for child in elem:
            child_tag = _strip_ns(child.tag)
            if child_tag == "UCAST_OKRSEK":
                registered_voters = int(child.attrib.get("ZAPSANI_VOLICI", 0))
                issued_envelopes = int(child.attrib.get("VYDANE_OBALKY", 0))
                valid_votes = int(child.attrib.get("PLATNE_HLASY", 0))
                pct_raw = child.attrib.get("UCAST_PROC")
                if pct_raw is not None:
                    try:
                        turnout_pct = float(pct_raw)
                    except ValueError:
                        turnout_pct = 0.0
                elif registered_voters > 0:
                    turnout_pct = round((issued_envelopes / registered_voters) * 100, 2)
                break

        # Resolve municipality name
        muni_name = None
        if municipality_names and municipality_code in municipality_names:
            muni_name = municipality_names[municipality_code]

        precinct_obj = PrecinctTimingResult(
            precinct_number=precinct_number,
            municipality_code=municipality_code,
            municipality_name=muni_name,
            district_number=district_number,
            processed_at=processed_at,
            processing_order=processing_order,
            is_repeated=is_repeated,
            registered_voters=registered_voters,
            issued_envelopes=issued_envelopes,
            turnout_pct=turnout_pct,
            valid_votes=valid_votes,
        )

        # De-duplicate within the batch: newer version (higher PORADI_ZPRAC) takes precedence
        key = (municipality_code, precinct_number)
        if key not in precincts_by_key or processing_order >= precincts_by_key[key].processing_order:
            precincts_by_key[key] = precinct_obj

    return generated_at, list(precincts_by_key.values())
