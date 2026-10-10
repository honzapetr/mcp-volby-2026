"""Parser for Senate election XML data."""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from src.models import (
    MunicipalitySenateResult,
    SenateCandidateResult,
    SenateDistrictBreakdownResponse,
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


def parse_senate_results(
    root: ET.Element,
    target_district: Optional[int] = None,
    candidate_registry: Optional[Dict[Tuple[int, int], Dict[str, str]]] = None,
) -> SenateOverviewResponse:
    """Parses Senate vysledky.xml and returns structured response."""
    # Lazy import to avoid circular dependencies
    if candidate_registry is None:
        try:
            from src.parsers.codebook_loader import codebook_index
            candidate_registry = codebook_index.senate_candidates
        except Exception:
            candidate_registry = {}

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

        # Extract turnout for Round 1 and Round 2
        turnout_r1 = TurnoutInfo(
            precincts_total=0,
            precincts_processed=0,
            precincts_processed_pct=0.0,
            registered_voters=0,
            issued_envelopes=0,
            turnout_pct=0.0,
            valid_votes=0,
        )
        turnout_r2: Optional[TurnoutInfo] = None

        for child in elem:
            if _strip_ns(child.tag) == "UCAST":
                kolo = child.attrib.get("KOLO", "1")
                t_info = TurnoutInfo(
                    precincts_total=int(child.attrib.get("OKRSKY_CELKEM", 0)),
                    precincts_processed=int(child.attrib.get("OKRSKY_ZPRAC", 0)),
                    precincts_processed_pct=float(child.attrib.get("OKRSKY_ZPRAC_PROC", 0.0)),
                    registered_voters=int(child.attrib.get("ZAPSANI_VOLICI", 0)),
                    issued_envelopes=int(child.attrib.get("VYDANE_OBALKY", 0)),
                    turnout_pct=float(child.attrib.get("UCAST_PROC", 0.0)),
                    valid_votes=int(child.attrib.get("PLATNE_HLASY", 0)),
                )
                if kolo == "2":
                    turnout_r2 = t_info
                else:
                    turnout_r1 = t_info

        # Extract candidates
        candidates: List[SenateCandidateResult] = []
        has_round_2_votes = False

        for child in elem:
            if _strip_ns(child.tag) == "KANDIDAT":
                cand_num = int(child.attrib.get("PORADOVE_CISLO", child.attrib.get("POR_CISLO", child.attrib.get("CKAND", 0))))
                
                # Check for party affiliations and names in registry or XML attributes
                cand_info = candidate_registry.get((district_num, cand_num), {}) if candidate_registry else {}
                first_name = child.attrib.get("JMENO") or cand_info.get("first_name", "")
                last_name = child.attrib.get("PRIJMENI") or cand_info.get("last_name", "")
                title_pre = child.attrib.get("TITULPRED") or cand_info.get("title_pre", "")
                title_post = child.attrib.get("TITULZA") or cand_info.get("title_post", "")

                party_name = (
                    cand_info.get("party_name")
                    or child.attrib.get("NAZEV_STRANY")
                    or child.attrib.get("NAZEV_VSTR")
                    or child.attrib.get("VSTRANA")
                    or None
                )
                nom_party = (
                    cand_info.get("nominating_party")
                    or child.attrib.get("NAVRH_STRANA")
                    or child.attrib.get("NAZEV_NSTR")
                    or None
                )
                pol_aff = (
                    cand_info.get("political_affiliation")
                    or child.attrib.get("POL_PRISL")
                    or child.attrib.get("NAZEV_PSTR")
                    or None
                )

                # Round 2 attributes
                v2_raw = child.attrib.get("HLASY_2KOLO")
                v2_pct_raw = child.attrib.get("HLASY_PROC_2KOLO")
                votes_r2 = int(v2_raw) if v2_raw is not None else None
                votes_pct_r2 = float(v2_pct_raw) if v2_pct_raw is not None else None
                elected_r2 = (
                    child.attrib.get("ZVOLEN_2KOLO") == "1"
                    or child.attrib.get("ZVOLEN") == "2"
                ) if (votes_r2 is not None or "ZVOLEN_2KOLO" in child.attrib) else None

                if votes_r2 is not None and votes_r2 > 0:
                    has_round_2_votes = True

                cand = SenateCandidateResult(
                    candidate_number=cand_num,
                    first_name=first_name,
                    last_name=last_name,
                    title_pre=title_pre,
                    title_post=title_post,
                    party_name=party_name,
                    nominating_party=nom_party,
                    political_affiliation=pol_aff,
                    votes_round_1=int(child.attrib.get("HLASY_1KOLO", 0)),
                    votes_pct_round_1=float(child.attrib.get("HLASY_PROC_1KOLO", 0.0)),
                    votes_round_2=votes_r2,
                    votes_pct_round_2=votes_pct_r2,
                    elected_round_2=elected_r2,
                )
                candidates.append(cand)

        # Sort candidates
        # If Round 2 votes exist, sort by Round 2 first, then Round 1
        if has_round_2_votes:
            candidates.sort(
                key=lambda c: (
                    c.votes_round_2 if c.votes_round_2 is not None else -1,
                    c.votes_round_1,
                    -c.candidate_number,
                ),
                reverse=True,
            )
        else:
            candidates.sort(key=lambda c: (c.votes_round_1, -c.candidate_number), reverse=True)

        is_r1_completed = (
            turnout_r1.precincts_processed == turnout_r1.precincts_total
            and turnout_r1.precincts_total > 0
        )
        has_round_2_node = turnout_r2 is not None
        is_r2_active = (
            has_round_2_node
            and (turnout_r2.precincts_processed > 0 or has_round_2_votes)
        )
        is_r2_completed = (
            has_round_2_node
            and turnout_r2.precincts_processed == turnout_r2.precincts_total
            and turnout_r2.precincts_total > 0
        )
        is_r2_pending = (
            has_round_2_node
            and not is_r2_active
            and not is_r2_completed
        )

        # Lead and cutoff margins
        lead_margin: Optional[dict] = None
        cutoff_margin: Optional[dict] = None
        lead_margin_votes: Optional[int] = None
        lead_margin_pct: Optional[float] = None
        cutoff_margin_votes: Optional[int] = None
        cutoff_margin_pct: Optional[float] = None

        if (is_r2_active or is_r2_completed) and has_round_2_votes and len(candidates) >= 2:
            c1 = candidates[0]
            c2 = candidates[1]
            if c1.votes_round_2 is not None and c2.votes_round_2 is not None:
                lead_margin_votes = c1.votes_round_2 - c2.votes_round_2
                lead_margin_pct = round(
                    (c1.votes_pct_round_2 or 0.0) - (c2.votes_pct_round_2 or 0.0), 2
                )
                lead_margin = {"votes": lead_margin_votes, "pct": lead_margin_pct}
        elif candidates and len(candidates) >= 2:
            lead_margin_votes = candidates[0].votes_round_1 - candidates[1].votes_round_1
            lead_margin_pct = round(
                candidates[0].votes_pct_round_1 - candidates[1].votes_pct_round_1, 2
            )
            lead_margin = {"votes": lead_margin_votes, "pct": lead_margin_pct}

            if len(candidates) >= 3:
                cutoff_margin_votes = candidates[1].votes_round_1 - candidates[2].votes_round_1
                cutoff_margin_pct = round(
                    candidates[1].votes_pct_round_1 - candidates[2].votes_pct_round_1, 2
                )
                cutoff_margin = {"votes": cutoff_margin_votes, "pct": cutoff_margin_pct}

        # Status summary and elected status
        status_summary = ""
        is_district_completed = False

        if is_r2_completed:
            is_district_completed = True
            completed_count += 1
            if candidates:
                if len(candidates) >= 2 and (candidates[0].votes_round_2 == candidates[1].votes_round_2):
                    status_summary = (
                        f"Rovnost hlasů ve 2. kole: {candidates[0].first_name} {candidates[0].last_name} "
                        f"a {candidates[1].first_name} {candidates[1].last_name} získali shodně "
                        f"{candidates[0].votes_round_2} hlasů ({candidates[0].votes_pct_round_2 or 50.0:.2f} %). "
                        f"O vítězi rozhodne los."
                    )
                else:
                    candidates[0].elected_round_2 = True
                    status_summary = (
                        f"Zvolen ve 2. kole: {candidates[0].first_name} {candidates[0].last_name} "
                        f"({candidates[0].votes_pct_round_2 or 0.0:.2f} %)."
                    )
        elif is_r2_active:
            is_district_completed = False
            leader = candidates[0] if candidates else None
            leader_str = (
                f", vede {leader.first_name} {leader.last_name} ({leader.votes_pct_round_2 or 0.0:.2f} %)"
                if leader
                else ""
            )
            status_summary = (
                f"Průběžné sčítání 2. kola: {turnout_r2.precincts_processed}/{turnout_r2.precincts_total} okrsků "
                f"({turnout_r2.precincts_processed_pct:.1f} %){leader_str}."
            )
        elif is_r2_pending:
            is_district_completed = False
            status_summary = (
                f"2. kolo – sčítání ještě nezačalo (0/{turnout_r2.precincts_total} okrsků)."
            )
        elif not is_r1_completed:
            is_district_completed = False
            if turnout_r1.precincts_processed == 0:
                status_summary = f"Sčítání ještě nezačalo (0/{turnout_r1.precincts_total} okrsků)."
            else:
                leader = candidates[0] if candidates else None
                leader_str = (
                    f", vede {leader.first_name} {leader.last_name} ({leader.votes_pct_round_1:.2f} %)"
                    if leader
                    else ""
                )
                status_summary = (
                    f"Průběžné sčítání 1. kola: {turnout_r1.precincts_processed}/{turnout_r1.precincts_total} okrsků "
                    f"({turnout_r1.precincts_processed_pct:.1f} %){leader_str}."
                )
        else:
            # Round 1 completed
            if candidates and candidates[0].votes_pct_round_1 > 50.0:
                candidates[0].elected_round_1 = True
                is_district_completed = True
                completed_count += 1
                status_summary = (
                    f"Zvolen v 1. kole: {candidates[0].first_name} {candidates[0].last_name} "
                    f"({candidates[0].votes_pct_round_1:.2f} %)."
                )
            else:
                is_district_completed = True  # 1st round counting is done
                completed_count += 1
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
                    status_summary = (
                        f"Vede: {candidates[0].first_name} {candidates[0].last_name} "
                        f"({candidates[0].votes_pct_round_1:.2f} %)."
                    )

        district_res = SenateDistrictResult(
            district_number=district_num,
            district_name=district_name,
            turnout=turnout_r1,
            turnout_round_2=turnout_r2,
            candidates=candidates,
            is_completed=is_district_completed,
            status_summary=status_summary,
            lead_margin=lead_margin,
            cutoff_margin=cutoff_margin,
            lead_margin_votes=lead_margin_votes,
            lead_margin_pct=lead_margin_pct,
            cutoff_margin_votes=cutoff_margin_votes,
            cutoff_margin_pct=cutoff_margin_pct,
        )
        districts_list.append(district_res)

    return SenateOverviewResponse(
        generated_at=generated_at,
        districts_total=len(districts_list),
        districts_completed=completed_count,
        districts=districts_list,
    )


def parse_senate_district_breakdown(
    root: ET.Element,
    district_num: int,
    district_name: str = "",
    candidate_registry: Optional[Dict[Tuple[int, int], Dict[str, str]]] = None,
) -> SenateDistrictBreakdownResponse:
    """Parses vysledky_obce_obvod_{num}.xml for municipalities within a Senate district."""
    if candidate_registry is None:
        try:
            from src.parsers.codebook_loader import codebook_index
            candidate_registry = codebook_index.senate_candidates
        except Exception:
            candidate_registry = {}

    generated_at = root.attrib.get("DATUM_CAS_GENEROVANI", "")
    
    # Try to find district name from root or OBVOD if not provided
    obvod_elem = None
    for child in root.iter():
        if _strip_ns(child.tag) == "OBVOD":
            obvod_elem = child
            break

    if obvod_elem is not None:
        if not district_name:
            district_name = obvod_elem.attrib.get("NAZEV", f"Obvod č. {district_num}")
        search_root = obvod_elem
    else:
        search_root = root

    municipalities: List[MunicipalitySenateResult] = []
    processed_count = 0

    for child in search_root.iter():
        if _strip_ns(child.tag) != "OBEC":
            continue

        kod_obce = child.attrib.get("KOD", child.attrib.get("KODOBCE", child.attrib.get("CISLO", "")))
        nazev_obce = child.attrib.get("NAZEV", child.attrib.get("NAZEVOBCE", ""))

        turnout = TurnoutInfo(
            precincts_total=0,
            precincts_processed=0,
            precincts_processed_pct=0.0,
            registered_voters=0,
            issued_envelopes=0,
            turnout_pct=0.0,
            valid_votes=0,
        )
        cand_list: List[SenateCandidateResult] = []

        for sub in child.iter():
            if sub is child:
                continue
            sub_tag = _strip_ns(sub.tag)
            if sub_tag == "UCAST":
                turnout = TurnoutInfo(
                    precincts_total=int(sub.attrib.get("OKRSKY_CELKEM", 0)),
                    precincts_processed=int(sub.attrib.get("OKRSKY_ZPRAC", 0)),
                    precincts_processed_pct=float(sub.attrib.get("OKRSKY_ZPRAC_PROC", 0.0)),
                    registered_voters=int(sub.attrib.get("ZAPSANI_VOLICI", 0)),
                    issued_envelopes=int(sub.attrib.get("VYDANE_OBALKY", 0)),
                    turnout_pct=float(sub.attrib.get("UCAST_PROC", 0.0)),
                    valid_votes=int(sub.attrib.get("PLATNE_HLASY", 0)),
                )
            elif sub_tag == "KANDIDAT":
                cand_num = int(sub.attrib.get("PORADOVE_CISLO", sub.attrib.get("POR_CISLO", sub.attrib.get("CKAND", 0))))
                cand_info = candidate_registry.get((district_num, cand_num), {}) if candidate_registry else {}

                first_name = sub.attrib.get("JMENO") or cand_info.get("first_name", "")
                last_name = sub.attrib.get("PRIJMENI") or cand_info.get("last_name", "")
                title_pre = sub.attrib.get("TITULPRED") or cand_info.get("title_pre", "")
                title_post = sub.attrib.get("TITULZA") or cand_info.get("title_post", "")

                party_name = (
                    cand_info.get("party_name")
                    or sub.attrib.get("NAZEV_STRANY")
                    or sub.attrib.get("NAZEV_VSTR")
                    or sub.attrib.get("VSTRANA")
                    or None
                )
                nom_party = (
                    cand_info.get("nominating_party")
                    or sub.attrib.get("NAVRH_STRANA")
                    or sub.attrib.get("NAZEV_NSTR")
                    or None
                )
                pol_aff = (
                    cand_info.get("political_affiliation")
                    or sub.attrib.get("POL_PRISL")
                    or sub.attrib.get("NAZEV_PSTR")
                    or None
                )

                v2_raw = sub.attrib.get("HLASY_2KOLO")
                v2_pct_raw = sub.attrib.get("HLASY_PROC_2KOLO")
                votes_r2 = int(v2_raw) if v2_raw is not None else None
                votes_pct_r2 = float(v2_pct_raw) if v2_pct_raw is not None else None

                cand = SenateCandidateResult(
                    candidate_number=cand_num,
                    first_name=first_name,
                    last_name=last_name,
                    title_pre=title_pre,
                    title_post=title_post,
                    party_name=party_name,
                    nominating_party=nom_party,
                    political_affiliation=pol_aff,
                    votes_round_1=int(sub.attrib.get("HLASY_1KOLO", 0)),
                    votes_pct_round_1=float(sub.attrib.get("HLASY_PROC_1KOLO", 0.0)),
                    votes_round_2=votes_r2,
                    votes_pct_round_2=votes_pct_r2,
                )
                cand_list.append(cand)

        # Sort candidates
        if any(c.votes_round_2 is not None for c in cand_list):
            cand_list.sort(
                key=lambda c: (
                    c.votes_round_2 if c.votes_round_2 is not None else -1,
                    c.votes_round_1,
                ),
                reverse=True,
            )
        else:
            cand_list.sort(key=lambda c: c.votes_round_1, reverse=True)

        leader = f"{cand_list[0].first_name} {cand_list[0].last_name}".strip() if cand_list else None
        if leader == "":
            leader = None

        if turnout.precincts_processed == turnout.precincts_total and turnout.precincts_total > 0:
            processed_count += 1

        municipalities.append(
            MunicipalitySenateResult(
                municipality_code=str(kod_obce),
                municipality_name=nazev_obce,
                turnout=turnout,
                candidates=cand_list,
                leader_name=leader,
            )
        )

    # Sort municipalities alphabetically by name
    municipalities.sort(key=lambda m: m.municipality_name)

    return SenateDistrictBreakdownResponse(
        district_number=district_num,
        district_name=district_name or f"Obvod č. {district_num}",
        generated_at=generated_at,
        municipalities_total=len(municipalities),
        municipalities_processed=processed_count,
        municipalities=municipalities,
    )
