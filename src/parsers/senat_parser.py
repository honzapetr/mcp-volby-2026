"""Parser for Senate election XML data."""

import logging
import xml.etree.ElementTree as ET
from typing import List, Optional

from src.models import (
    SenateCandidateResult,
    SenateDistrictResult,
    SenateOverviewResponse,
    TurnoutInfo,
)

logger = logging.getLogger(__name__)


def _strip_ns(tag: str) -> str:
    """Removes XML namespace prefix if present."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_senate_results(root: ET.Element, target_district: Optional[int] = None) -> SenateOverviewResponse:
    """Parses Senate vysledky.xml and returns structured response."""
    generated_at = root.attrib.get("DATUM_CAS_GENEROVANI", "")
    districts_list: List[SenateDistrictResult] = []
    completed_count = 0

    for elem in root:
        if _strip_ns(elem.tag) != "OBVOD":
            continue

        district_num = int(elem.attrib.get("CISLO", 0))
        district_name = elem.attrib.get("NAZEV", "")

        # If user asked for a specific district, skip others
        if target_district is not None and district_num != target_district:
            continue

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

        for child in elem:
            if _strip_ns(child.tag) == "UCAST":
                turnout = TurnoutInfo(
                    precincts_total=int(child.attrib.get("OKRSKY_CELKEM", 0)),
                    precincts_processed=int(child.attrib.get("OKRSKY_ZPRAC", 0)),
                    precincts_processed_pct=float(child.attrib.get("OKRSKY_ZPRAC_PROC", 0.0)),
                    registered_voters=int(child.attrib.get("ZAPSANI_VOLICI", 0)),
                    issued_envelopes=int(child.attrib.get("VYDANE_OBALKY", 0)),
                    turnout_pct=float(child.attrib.get("UCAST_PROC", 0.0)),
                    valid_votes=int(child.attrib.get("PLATNE_HLASY", 0)),
                )
                break

        # Extract candidates
        candidates: List[SenateCandidateResult] = []
        for child in elem:
            if _strip_ns(child.tag) == "KANDIDAT":
                cand = SenateCandidateResult(
                    candidate_number=int(child.attrib.get("PORADOVE_CISLO", 0)),
                    first_name=child.attrib.get("JMENO", ""),
                    last_name=child.attrib.get("PRIJMENI", ""),
                    title_pre=child.attrib.get("TITULPRED", ""),
                    title_post=child.attrib.get("TITULZA", ""),
                    votes_round_1=int(child.attrib.get("HLASY_1KOLO", 0)),
                    votes_pct_round_1=float(child.attrib.get("HLASY_PROC_1KOLO", 0.0)),
                )
                candidates.append(cand)

        # Sort candidates: by votes descending, then by number
        candidates.sort(key=lambda c: (c.votes_round_1, -c.candidate_number), reverse=True)

        is_completed = (
            turnout.precincts_processed == turnout.precincts_total and turnout.precincts_total > 0
        )
        if is_completed:
            completed_count += 1

        # Determine round 1 winner or advancing candidates
        status_summary = ""
        if turnout.precincts_processed == 0:
            status_summary = f"Sčítání ještě nezačalo (0/{turnout.precincts_total} okrsků)."
        elif is_completed:
            if candidates and candidates[0].votes_pct_round_1 > 50.0:
                candidates[0].elected_round_1 = True
                status_summary = (
                    f"Zvolen v 1. kole: {candidates[0].first_name} {candidates[0].last_name} "
                    f"({candidates[0].votes_pct_round_1:.2f} %)."
                )
            else:
                if len(candidates) >= 2:
                    candidates[0].advances_to_round_2 = True
                    candidates[1].advances_to_round_2 = True
                    status_summary = (
                        f"Postup do 2. kola: 1. {candidates[0].first_name} {candidates[0].last_name} "
                        f"({candidates[0].votes_pct_round_1:.2f} %), 2. {candidates[1].first_name} "
                        f"{candidates[1].last_name} ({candidates[1].votes_pct_round_1:.2f} %)."
                    )
                elif candidates:
                    candidates[0].advances_to_round_2 = True
                    status_summary = f"Vede: {candidates[0].first_name} {candidates[0].last_name} ({candidates[0].votes_pct_round_1:.2f} %)."
        else:
            leader = candidates[0] if candidates else None
            leader_str = f", vede {leader.first_name} {leader.last_name} ({leader.votes_pct_round_1:.2f} %)" if leader else ""
            status_summary = (
                f"Průběžné sčítání: {turnout.precincts_processed}/{turnout.precincts_total} okrsků "
                f"({turnout.precincts_processed_pct:.1f} %){leader_str}."
            )

        district_res = SenateDistrictResult(
            district_number=district_num,
            district_name=district_name,
            turnout=turnout,
            candidates=candidates,
            is_completed=is_completed,
            status_summary=status_summary,
        )
        districts_list.append(district_res)

    return SenateOverviewResponse(
        generated_at=generated_at,
        districts_total=len(districts_list),
        districts_completed=completed_count,
        districts=districts_list,
    )
