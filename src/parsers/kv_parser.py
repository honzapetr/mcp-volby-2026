"""Parser for Municipal elections (volby do zastupitelstev obcí) XML data."""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from src.models import (
    MunicipalCandidateResult,
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


def _parse_candidate_elem(
    elem: ET.Element,
    party_name: Optional[str],
    party_id: Optional[int],
    kod_zastup: str,
    tag: str,
    candidate_registry: Optional[Dict[Tuple[str, int, int], Dict[str, str]]] = None,
) -> MunicipalCandidateResult:
    """Parses an individual municipal candidate or elected representative XML element."""
    cand_num_raw = (
        elem.attrib.get("PORADOVE_CISLO")
        or elem.attrib.get("POR_CISLO")
        or elem.attrib.get("CKAND", "0")
    )
    cand_num = int(cand_num_raw) if str(cand_num_raw).isdigit() else 0

    first_name = elem.attrib.get("JMENO", "")
    last_name = elem.attrib.get("PRIJMENI", "")
    title_pre = elem.attrib.get("TITULPRED", "")
    title_post = elem.attrib.get("TITULZA", "")

    # If name details are missing in XML, attempt lookup in candidate registry
    if (not first_name or not last_name) and candidate_registry:
        reg_info = candidate_registry.get((str(kod_zastup).zfill(6), party_id or 0, cand_num))
        if reg_info:
            first_name = first_name or reg_info.get("first_name", "")
            last_name = last_name or reg_info.get("last_name", "")
            title_pre = title_pre or reg_info.get("title_pre", "")
            title_post = title_post or reg_info.get("title_post", "")
            if not party_name and reg_info.get("party_name"):
                party_name = reg_info.get("party_name")

    votes = int(elem.attrib.get("HLASY", 0))
    votes_pct = float(elem.attrib.get("HLASY_PROC", 0.0))

    is_elected = (
        tag in ("ZASTUPITEL", "VOLENY_ZASTUPITEL")
        or elem.attrib.get("MANDAT", "").upper() == "A"
        or elem.attrib.get("ZVOLEN", "") == "1"
    )

    order_raw = elem.attrib.get("PORADI_ZVOLENI") or elem.attrib.get("PORADI")
    order_elected = int(order_raw) if order_raw is not None and str(order_raw).isdigit() else None

    mandat_attr = elem.attrib.get("MANDAT", "").upper()
    zvolen_attr = elem.attrib.get("ZVOLEN", "")
    if is_elected:
        mandate_status = "Zvolen"
    elif mandat_attr == "N" or zvolen_attr == "0":
        mandate_status = "Náhradník"
    else:
        mandate_status = "Bez mandátu"

    return MunicipalCandidateResult(
        candidate_number=cand_num,
        first_name=first_name,
        last_name=last_name,
        title_pre=title_pre,
        title_post=title_post,
        party_name=party_name,
        party_id=party_id,
        votes=votes,
        votes_pct=votes_pct,
        is_elected=is_elected,
        order_elected=order_elected,
        mandate_status=mandate_status,
    )


def parse_municipal_results(
    root: ET.Element,
    candidate_registry: Optional[Dict[Tuple[str, int, int], Dict[str, str]]] = None,
) -> MunicipalResultResponse:
    """Parses vysledky_obec_XXXXXX.xml for a specific town or city council."""
    # Lazy import candidate registry from codebooks if not passed explicitly
    if candidate_registry is None:
        try:
            from src.parsers.codebook_loader import codebook_index
            candidate_registry = codebook_index.municipal_candidates
        except Exception:
            candidate_registry = {}

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
    all_elected: List[MunicipalCandidateResult] = []
    unattached_candidates: List[MunicipalCandidateResult] = []

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
            list_number = int(child.attrib.get("POR_STR_HLAS_LIST", 0))
            party_id = int(child.attrib.get("VSTRANA", 0))
            party_name = child.attrib.get("NAZEV_STRANY", "")
            votes = int(child.attrib.get("HLASY", 0))
            votes_pct = float(child.attrib.get("HLASY_PROC", 0.0))
            seats_won = int(child.attrib.get("ZASTUPITELE_POCET", 0))
            seats_pct = float(child.attrib.get("ZASTUPITELE_PROC", 0.0))
            candidates_count = int(child.attrib.get("KANDIDATU_POCET", 0))

            party_candidates: List[MunicipalCandidateResult] = []
            party_elected: List[MunicipalCandidateResult] = []

            # Parse candidate/representative elements nested under this VOLEBNI_STRANA
            for sub in child:
                sub_tag = _strip_ns(sub.tag)
                if sub_tag in ("ZASTUPITEL", "KANDIDAT", "VOLENY_ZASTUPITEL"):
                    cand = _parse_candidate_elem(
                        sub,
                        party_name=party_name,
                        party_id=party_id,
                        kod_zastup=kod_zastup,
                        tag=sub_tag,
                        candidate_registry=candidate_registry,
                    )
                    party_candidates.append(cand)
                    if cand.is_elected:
                        party_elected.append(cand)
                        all_elected.append(cand)

            # Sort party candidates: elected first, then by votes descending
            party_candidates.sort(
                key=lambda c: (
                    0 if c.is_elected else 1,
                    c.order_elected if c.order_elected is not None else 9999,
                    -c.votes,
                    c.candidate_number,
                )
            )

            party = MunicipalPartyResult(
                list_number=list_number,
                party_id=party_id,
                party_name=party_name,
                votes=votes,
                votes_pct=votes_pct,
                seats_won=seats_won,
                seats_pct=seats_pct,
                candidates_count=candidates_count,
                candidates=party_candidates,
                elected_candidates=party_elected,
            )
            parties.append(party)

    # Sort parties: by votes descending, then seats won, then list number
    parties.sort(key=lambda p: (p.votes, p.seats_won, -p.list_number), reverse=True)

    # Sort all elected council members: by order of election, then votes descending
    all_elected.sort(
        key=lambda c: (
            c.order_elected if c.order_elected is not None else 9999,
            -c.votes,
            c.party_name or "",
        )
    )

    # Check completeness
    is_completed = je_spocteno or (
        turnout.precincts_processed == turnout.precincts_total and turnout.precincts_total > 0
    )

    top_party_name = parties[0].party_name if (parties and parties[0].votes > 0) else None
    winner = top_party_name if is_completed else None
    leading_party = top_party_name if not is_completed else None

    if voleno_zastup == 0 and parties:
        voleno_zastup = sum(p.seats_won for p in parties)

    # Calculate majority seats needed
    majority_seats = (voleno_zastup // 2 + 1) if voleno_zastup > 0 else 0

    # Calculate wasted votes %
    if is_completed:
        # After full counting, sum of vote % for parties that won 0 seats
        wasted_votes_pct = round(
            sum(p.votes_pct for p in parties if p.seats_won == 0),
            2,
        )
    else:
        # During counting, seats are not yet allocated (seats_won == 0 for all parties).
        # Wasted votes are computed from parties failing the 5% legal threshold.
        wasted_votes_pct = round(
            sum(p.votes_pct for p in parties if p.votes_pct < 5.0),
            2,
        )

    counting_status = (
        "Sčítání dokončeno" if is_completed
        else (
            f"Probíhá sčítání ({turnout.precincts_processed}/{turnout.precincts_total} okrsků, "
            f"{turnout.precincts_processed_pct:.1f} % - průběžně vede {leading_party or 'nikdo'})"
            if turnout.precincts_processed > 0
            else "Sčítání ještě nezačalo (0 okrsků)"
        )
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
        leading_party=leading_party,
        majority_seats=majority_seats,
        wasted_votes_pct=wasted_votes_pct,
        counting_status=counting_status,
        elected_representatives=all_elected,
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
