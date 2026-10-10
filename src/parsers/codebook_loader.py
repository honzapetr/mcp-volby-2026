"""Loader and search index for municipalities and Senate electoral districts.

Provides fast, accent-insensitive search and resolution between names and CSU codes.
Includes bundled definitions of all 81 Senate districts (including the 27 for 2026)
and major Czech statutory cities, with support for downloading the full 6,249
municipalities registry from CSU open data.
"""

import asyncio
import json
import logging
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.client_csu import csu_client
from src.config import settings
from src.models import SearchResultItem, SearchResultResponse

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalizes string for search: removes diacritics/accents, converts to lower case."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ASCII", "ignore").decode("utf-8").lower().strip()


# The 27 Senate districts contested in 2026 (modulo 3 = 0, starting from district 3)
SENATE_2026_DISTRICTS: Dict[int, str] = {
    3: "Cheb",
    6: "Louny",
    9: "Plzeň-město",
    12: "Strakonice",
    15: "Pelhřimov",
    18: "Příbram",
    21: "Praha 5",
    24: "Praha 9",
    27: "Praha 1",
    30: "Kladno",
    33: "Děčín",
    36: "Česká Lípa",
    39: "Trutnov",
    42: "Kolín",
    45: "Hradec Králové",
    48: "Rychnov nad Kněžnou",
    51: "Žďár nad Sázavou",
    54: "Znojmo",
    57: "Vyškov",
    60: "Brno-město",
    63: "Přerov",
    66: "Olomouc",
    69: "Frýdek-Místek",
    72: "Ostrava-město",
    75: "Karviná",
    78: "Zlín",
    81: "Uherské Hradiště",
}

# Major statutory cities and county seats in the Czech Republic
MAJOR_CITIES: List[Tuple[str, str, str, str]] = [
    # (code, name, district_nuts, description)
    ("554782", "Praha", "CZ0100", "Hlavní město Praha (statutární město a kraj)"),
    ("582786", "Brno", "CZ0642", "Statutární město Brno (Jihomoravský kraj)"),
    ("554821", "Ostrava", "CZ0806", "Statutární město Ostrava (Moravskoslezský kraj)"),
    ("554791", "Plzeň", "CZ0323", "Statutární město Plzeň (Plzeňský kraj)"),
    ("563889", "Liberec", "CZ0513", "Statutární město Liberec (Liberecký kraj)"),
    ("500496", "Olomouc", "CZ0712", "Statutární město Olomouc (Olomoucký kraj)"),
    ("554804", "Ústí nad Labem", "CZ0427", "Statutární město Ústí nad Labem (Ústecký kraj)"),
    ("544256", "České Budějovice", "CZ0311", "Statutární město České Budějovice (Jihočeský kraj)"),
    ("569810", "Hradec Králové", "CZ0521", "Statutární město Hradec Králové (Královéhradecký kraj)"),
    ("555134", "Pardubice", "CZ0532", "Statutární město Pardubice (Pardubický kraj)"),
    ("585068", "Zlín", "CZ0724", "Statutární město Zlín (Zlínský kraj)"),
    ("552356", "Havířov", "CZ0803", "Statutární město Havířov (Moravskoslezský kraj)"),
    ("532053", "Kladno", "CZ0203", "Statutární město Kladno (Středočeský kraj)"),
    ("567027", "Most", "CZ0425", "Statutární město Most (Ústecký kraj)"),
    ("505927", "Opava", "CZ0805", "Statutární město Opava (Moravskoslezský kraj)"),
    ("598089", "Frýdek-Místek", "CZ0802", "Statutární město Frýdek-Místek (Moravskoslezský kraj)"),
    ("598917", "Karviná", "CZ0803", "Statutární město Karviná (Moravskoslezský kraj)"),
    ("586846", "Jihlava", "CZ0632", "Statutární město Jihlava (Kraj Vysočina)"),
    ("567442", "Teplice", "CZ0426", "Statutární město Teplice (Ústecký kraj)"),
    ("562335", "Děčín", "CZ0421", "Statutární město Děčín (Ústecký kraj)"),
    ("554961", "Karlovy Vary", "CZ0412", "Statutární město Karlovy Vary (Karlovarský kraj)"),
    ("562971", "Chomutov", "CZ0422", "Statutární město Chomutov (Ústecký kraj)"),
    ("563510", "Jablonec nad Nisou", "CZ0512", "Statutární město Jablonec nad Nisou (Liberecký kraj)"),
    ("535419", "Mladá Boleslav", "CZ0207", "Statutární město Mladá Boleslav (Středočeský kraj)"),
    ("589250", "Prostějov", "CZ0713", "Statutární město Prostějov (Olomoucký kraj)"),
    ("512800", "Přerov", "CZ0714", "Statutární město Přerov (Olomoucký kraj)"),
    ("598810", "Třinec", "CZ0802", "Statutární město Třinec (Moravskoslezský kraj)"),
    ("529303", "Benešov", "CZ0201", "Město Benešov (Středočeský kraj)"),
    ("533165", "Kolín", "CZ0204", "Město Kolín (Středočeský kraj)"),
    ("533955", "Kutná Hora", "CZ0205", "Město Kutná Hora (Středočeský kraj)"),
    ("535672", "Nymburk", "CZ0208", "Město Nymburk (Středočeský kraj)"),
    ("539911", "Příbram", "CZ020B", "Město Příbram (Středočeský kraj)"),
    ("541290", "Rakovník", "CZ020C", "Město Rakovník (Středočeský kraj)"),
    ("550540", "Písek", "CZ0314", "Město Písek (Jihočeský kraj)"),
    ("550787", "Prachatice", "CZ0315", "Město Prachatice (Jihočeský kraj)"),
    ("550884", "Strakonice", "CZ0316", "Město Strakonice (Jihočeský kraj)"),
    ("552101", "Tábor", "CZ0317", "Město Tábor (Jihočeský kraj)"),
    ("553557", "Klatovy", "CZ0322", "Město Klatovy (Plzeňský kraj)"),
    ("554481", "Rokycany", "CZ0326", "Město Rokycany (Plzeňský kraj)"),
    ("560715", "Cheb", "CZ0411", "Město Cheb (Karlovarský kraj)"),
    ("560286", "Sokolov", "CZ0413", "Město Sokolov (Karlovarský kraj)"),
    ("564559", "Česká Lípa", "CZ0511", "Město Česká Lípa (Liberecký kraj)"),
    ("573752", "Trutnov", "CZ0525", "Město Trutnov (Královéhradecký kraj)"),
    ("572241", "Chrudim", "CZ0531", "Město Chrudim (Pardubický kraj)"),
    ("580791", "Svitavy", "CZ0533", "Město Svitavy (Pardubický kraj)"),
    ("587001", "Třebíč", "CZ0634", "Město Třebíč (Kraj Vysočina)"),
    ("595209", "Žďár nad Sázavou", "CZ0635", "Město Žďár nad Sázavou (Kraj Vysočina)"),
    ("584444", "Břeclav", "CZ0644", "Město Břeclav (Jihomoravský kraj)"),
    ("586021", "Hodonín", "CZ0645", "Město Hodonín (Jihomoravský kraj)"),
    ("592889", "Vyškov", "CZ0646", "Město Vyškov (Jihomoravský kraj)"),
    ("593711", "Znojmo", "CZ0647", "Město Znojmo (Jihomoravský kraj)"),
    ("536385", "Jeseník", "CZ0711", "Město Jeseník (Olomoucký kraj)"),
    ("523704", "Šumperk", "CZ0715", "Město Šumperk (Olomoucký kraj)"),
    ("591939", "Kroměříž", "CZ0721", "Město Kroměříž (Zlínský kraj)"),
    ("592005", "Uherské Hradiště", "CZ0722", "Město Uherské Hradiště (Zlínský kraj)"),
    ("542385", "Vsetín", "CZ0723", "Město Vsetín (Zlínský kraj)"),
    ("597180", "Bruntál", "CZ0801", "Město Bruntál (Moravskoslezský kraj)"),
    ("599549", "Nový Jičín", "CZ0804", "Město Nový Jičín (Moravskoslezský kraj)"),
]


class CodebookIndex:
    """In-memory searchable index for municipalities and Senate districts."""

    def __init__(self):
        self.municipalities: Dict[str, SearchResultItem] = {}  # code -> item
        self.senate_districts: Dict[int, SearchResultItem] = {}  # district_num -> item
        self.senate_candidates: Dict[Tuple[int, int], Dict[str, str]] = {}  # (district, cand_num) -> info
        self.municipal_candidates: Dict[Tuple[str, int, int], Dict[str, Any]] = {}  # (kod_zastup, party_id_or_list, cand_num) -> info
        self.municipal_candidates_by_party: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}  # (kod_zastup, list_num) -> [cands]
        self.political_affiliations: Dict[int, str] = {}  # pstrana_id -> name
        self.nominating_parties: Dict[int, str] = {}  # nstrana_id -> name
        self.municipal_parties: Dict[Tuple[str, int], str] = {}  # (kod_zastup, list_num) -> party_name
        self._initialized = False

    def initialize_defaults(self):
        """Populates index with bundled Senate districts and major cities."""
        if self._initialized:
            return

        # Add 2026 Senate districts
        for num, name in SENATE_2026_DISTRICTS.items():
            self.senate_districts[num] = SearchResultItem(
                item_type="senat",
                code=str(num),
                name=f"Obvod č. {num} - {name}",
                description=f"Senátní volební obvod č. {num} ({name}) - volí se v roce 2026",
            )

        # Add major cities
        for code, name, nuts, desc in MAJOR_CITIES:
            self.municipalities[code] = SearchResultItem(
                item_type="obec",
                code=code,
                name=name,
                district_nuts=nuts,
                description=desc,
            )

        self._initialized = True
        logger.info(
            "Initialized default codebook index with %d Senate districts and %d municipalities.",
            len(self.senate_districts),
            len(self.municipalities),
        )

    async def load_senate_candidates(self):
        """Optionally loads candidate party affiliations from CSU Senate registry (serk.json)."""
        candidate_urls = [
            f"{settings.CSU_BASE_URL}/opendata/se2026/SE2026reg20261007_json.zip",
            "https://volby.cz/opendata/se2026/SE2026reg20261007_json.zip",
            f"{settings.CSU_BASE_URL}/opendata/senat/{settings.SENAT_ELECTION_CODE}/SE2026reg20261007_json.zip",
            f"{settings.CSU_BASE_URL}/opendata/senat/SE2026reg20261007_json.zip",
        ]
        data = None
        for url in candidate_urls:
            try:
                data = await csu_client.get_zip_json(url, "serk.json", ttl=86400, timeout=settings.CODEBOOK_ZIP_TIMEOUT_SECONDS)
                if data:
                    break
            except Exception:
                continue

        if not data:
            return

        items = (data.get("polozky") or data.get("položky") or []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        count = 0
        for item in items:
            obvod_val = item.get("OBVOD", item.get("obvod", item.get("CISLO_OBVODU", 0)))
            ckand_val = item.get("CKAND", item.get("POR_CISLO", item.get("poradove_cislo", item.get("PORADOVE_CISLO", item.get("KANDIDAT", 0)))))
            try:
                obvod = int(obvod_val)
                ckand = int(ckand_val)
            except (ValueError, TypeError):
                continue

            first_name = item.get("JMENO", item.get("jmeno", ""))
            last_name = item.get("PRIJMENI", item.get("prijmeni", ""))
            title_pre = item.get("TITULPRED", item.get("titulpred", ""))
            title_post = item.get("TITULZA", item.get("titulza", ""))

            party_name = item.get("NAZEV_VSTR", item.get("NAZ_VSTR", item.get("VSTRANA_NAZEV", item.get("NAZEV_STRANY", ""))))
            nom_party = item.get("NAZEV_NSTR", item.get("NAZ_NSTR", item.get("NAVRH_STR_NAZEV", item.get("NAVRH_STRANA", ""))))
            pol_aff = item.get("NAZEV_PSTR", item.get("NAZ_PSTR", item.get("POL_PRISL_NAZEV", item.get("POL_PRISL", ""))))

            if obvod and ckand:
                self.senate_candidates[(obvod, ckand)] = {
                    "first_name": str(first_name or ""),
                    "last_name": str(last_name or ""),
                    "title_pre": str(title_pre or ""),
                    "title_post": str(title_post or ""),
                    "party_name": str(party_name or ""),
                    "nominating_party": str(nom_party or ""),
                    "political_affiliation": str(pol_aff or ""),
                }
                count += 1

        logger.info("Loaded %d Senate candidates from CSU open data (serk.json).", count)

    def get_candidate_affiliation(self, district_num: int, candidate_num: int) -> Dict[str, str]:
        """Returns candidate party affiliation info if available."""
        return self.senate_candidates.get((district_num, candidate_num), {
            "first_name": "",
            "last_name": "",
            "title_pre": "",
            "title_post": "",
            "party_name": "",
            "nominating_party": "",
            "political_affiliation": "",
        })

    def get_municipal_candidate_info(
        self, kod_zastup: str, party_id: int, candidate_num: int, list_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Returns candidate details from municipal candidate registry (kvrk.json)."""
        kod_clean = str(kod_zastup).strip().zfill(6)
        cand = self.municipal_candidates.get((kod_clean, party_id, candidate_num))
        if not cand and list_number is not None:
            cand = self.municipal_candidates.get((kod_clean, list_number, candidate_num))
        return cand or {
            "first_name": "",
            "last_name": "",
            "title_pre": "",
            "title_post": "",
            "party_name": "",
            "nominating_party": "",
            "political_affiliation": "",
            "age": None,
            "occupation": "",
        }

    def get_municipal_party_candidates(
        self, kod_zastup: str, list_number: int, party_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Returns all registered candidates for a party/list in a municipality sorted by number."""
        kod_clean = str(kod_zastup).strip().zfill(6)
        cands = self.municipal_candidates_by_party.get((kod_clean, list_number))
        if not cands and party_id is not None:
            cands = self.municipal_candidates_by_party.get((kod_clean, party_id))
        if cands:
            return sorted(cands, key=lambda c: c.get("candidate_number", 0))
        return []

    async def load_municipal_candidates(self):
        """Optionally loads candidate registry for municipal elections from CSU open data (kvrk.json, kvros.json)."""
        candidate_urls = [
            f"{settings.CSU_BASE_URL}/opendata/{settings.KV_VERSION}/KV2026reg20261007_json.zip",
            f"https://volby.cz/opendata/{settings.KV_VERSION}/KV2026reg20261007_json.zip",
        ]

        # Load party registered names for municipalities from kvros.json
        for url in candidate_urls:
            try:
                ros_data = await csu_client.get_zip_json(url, "kvros.json", ttl=86400, timeout=settings.CODEBOOK_ZIP_TIMEOUT_SECONDS)
                if ros_data:
                    items = (ros_data.get("polozky") or ros_data.get("položky") or []) if isinstance(ros_data, dict) else (ros_data if isinstance(ros_data, list) else [])
                    for item in items:
                        raw_kod = item.get("KODZASTUP", 0)
                        raw_list = item.get("POR_STR_HL", 0)
                        p_name = item.get("NAZEVCELK") or item.get("ZKRATKAO30", "")
                        try:
                            kod = str(raw_kod).strip().zfill(6)
                            list_num = int(raw_list)
                            if kod and list_num:
                                self.municipal_parties[(kod, list_num)] = str(p_name).strip()
                        except (ValueError, TypeError):
                            continue
                    break
            except Exception:
                continue

        # Load municipal candidates from kvrk.json
        data = None
        for url in candidate_urls:
            try:
                data = await csu_client.get_zip_json(url, "kvrk.json", ttl=86400, timeout=settings.CODEBOOK_ZIP_TIMEOUT_SECONDS)
                if data:
                    break
            except Exception:
                continue

        if not data:
            return

        items = (data.get("polozky") or data.get("položky") or []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        count = 0
        for item in items:
            raw_kod = item.get("KODZASTUP", item.get("kod_zastup", 0))
            raw_list = item.get("POR_STR_HL", item.get("POR_STR_HLAS_LIST", 0))
            raw_party = item.get("OSTRANA", item.get("VSTRANA", raw_list))
            raw_ckand = item.get("PORCISLO", item.get("POR_CISLO", item.get("CKAND", item.get("poradove_cislo", 0))))
            try:
                kod = str(raw_kod).strip().zfill(6)
                list_num = int(raw_list)
                party_id = int(raw_party)
                ckand = int(raw_ckand)
            except (ValueError, TypeError):
                continue

            first_name = item.get("JMENO", item.get("jmeno", ""))
            last_name = item.get("PRIJMENI", item.get("prijmeni", ""))
            title_pre = item.get("TITULPRED", item.get("titulpred", ""))
            title_post = item.get("TITULZA", item.get("titulza", ""))

            pstrana_raw = item.get("PSTRANA")
            pol_aff = item.get("NAZEV_PSTR", "")
            if not pol_aff and pstrana_raw is not None:
                try:
                    pol_aff = self.political_affiliations.get(int(pstrana_raw), str(pstrana_raw))
                except (ValueError, TypeError):
                    pol_aff = str(pstrana_raw)

            nstrana_raw = item.get("NSTRANA")
            nom_party = item.get("NAZEV_NSTR", "")
            if not nom_party and nstrana_raw is not None:
                try:
                    nom_party = self.nominating_parties.get(int(nstrana_raw), str(nstrana_raw))
                except (ValueError, TypeError):
                    nom_party = str(nstrana_raw)

            party_name = (
                item.get("NAZEV_VSTR", "")
                or item.get("NAZEV_STRANY", "")
                or self.municipal_parties.get((kod, list_num), "")
            )

            age_raw = item.get("VEK")
            age = int(age_raw) if age_raw is not None and str(age_raw).isdigit() else None
            occupation = item.get("POVOLANI", "")

            if kod and ckand:
                cand_info = {
                    "candidate_number": ckand,
                    "first_name": str(first_name or ""),
                    "last_name": str(last_name or ""),
                    "title_pre": str(title_pre or ""),
                    "title_post": str(title_post or ""),
                    "party_name": str(party_name or ""),
                    "nominating_party": str(nom_party or ""),
                    "political_affiliation": str(pol_aff or ""),
                    "age": age,
                    "occupation": str(occupation or ""),
                }
                # Index by party_id and list_number
                self.municipal_candidates[(kod, party_id, ckand)] = cand_info
                if list_num != party_id:
                    self.municipal_candidates[(kod, list_num, ckand)] = cand_info

                # Index by party list
                key_list = (kod, list_num)
                if key_list not in self.municipal_candidates_by_party:
                    self.municipal_candidates_by_party[key_list] = []
                self.municipal_candidates_by_party[key_list].append(cand_info)

                if party_id != list_num:
                    key_party = (kod, party_id)
                    if key_party not in self.municipal_candidates_by_party:
                        self.municipal_candidates_by_party[key_party] = []
                    self.municipal_candidates_by_party[key_party].append(cand_info)

                count += 1

        logger.info("Loaded %d municipal candidates from CSU open data (kvrk.json).", count)

    async def load_remote_codebooks(self):
        """Optionally loads complete nationwide municipality list and codebooks from CSU open data."""
        try:
            self.initialize_defaults()
            ciselniky_urls = [
                f"{settings.CSU_BASE_URL}/opendata/{settings.KV_VERSION}/KV2026ciselniky20261007_json.zip",
                f"https://volby.cz/opendata/{settings.KV_VERSION}/KV2026ciselniky20261007_json.zip",
            ]

            # Load political affiliations (cpp.json)
            for url in ciselniky_urls:
                try:
                    cpp_data = await csu_client.get_zip_json(url, "cpp.json", ttl=86400, timeout=settings.CODEBOOK_ZIP_TIMEOUT_SECONDS)
                    if cpp_data:
                        items = (cpp_data.get("polozky") or cpp_data.get("položky") or []) if isinstance(cpp_data, dict) else (cpp_data if isinstance(cpp_data, list) else [])
                        for item in items:
                            pid = item.get("PSTRANA")
                            pname = item.get("ZKRATKAP30") or item.get("NAZEV_PSTR", "")
                            if pid is not None:
                                try:
                                    self.political_affiliations[int(pid)] = str(pname).strip()
                                except (ValueError, TypeError):
                                    pass
                        break
                except Exception:
                    continue

            # Load nominating parties (cns.json)
            for url in ciselniky_urls:
                try:
                    cns_data = await csu_client.get_zip_json(url, "cns.json", ttl=86400, timeout=settings.CODEBOOK_ZIP_TIMEOUT_SECONDS)
                    if cns_data:
                        items = (cns_data.get("polozky") or cns_data.get("položky") or []) if isinstance(cns_data, dict) else (cns_data if isinstance(cns_data, list) else [])
                        for item in items:
                            nid = item.get("NSTRANA")
                            nname = item.get("ZKRATKAN30") or item.get("NAZEV_NSTR", "")
                            if nid is not None:
                                try:
                                    self.nominating_parties[int(nid)] = str(nname).strip()
                                except (ValueError, TypeError):
                                    pass
                        break
                except Exception:
                    continue

            # Load municipalities (kvcoco.json)
            data = None
            for url in ciselniky_urls:
                try:
                    data = await csu_client.get_zip_json(url, "kvcoco.json", ttl=86400, timeout=settings.CODEBOOK_ZIP_TIMEOUT_SECONDS)
                    if data:
                        break
                except Exception:
                    continue

            if data:
                items = (data.get("polozky") or data.get("položky") or []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                count_added = 0
                for item in items:
                    raw_kod = item.get("KODZASTUP", item.get("kód", item.get("kod", "")))
                    kod = str(raw_kod).strip().zfill(6)
                    nazev = item.get("NAZEVZAST", "")
                    if not nazev and isinstance(item.get("název"), dict):
                        nazev = item["název"].get("cs", "")
                    elif not nazev and isinstance(item.get("nazev"), dict):
                        nazev = item["nazev"].get("cs", "")
                    elif not nazev:
                        nazev = str(item.get("název", item.get("nazev", ""))).strip()
                    nuts = str(item.get("NUTS", item.get("nuts", "")))

                    if kod and nazev and kod != "000000":
                        # Protect curated MAJOR_CITIES clean names from being overwritten by verbose official names
                        if kod not in self.municipalities:
                            self.municipalities[kod] = SearchResultItem(
                                item_type="obec",
                                code=kod,
                                name=nazev,
                                district_nuts=nuts if nuts else None,
                                description=f"Obec / zastupitelstvo {nazev} (kód {kod})",
                            )
                            count_added += 1

                logger.info("Loaded %d additional municipalities from CSU open data.", count_added)
        except Exception as exc:
            logger.warning(
                "Could not load extended remote codebooks from CSU (%s). Using bundled defaults.",
                exc,
            )

        # Also load Senate candidate affiliations
        try:
            await self.load_senate_candidates()
        except Exception as exc:
            logger.warning("Could not load Senate candidates (%s).", exc)

        # Also load municipal candidate registry
        try:
            await self.load_municipal_candidates()
        except Exception as exc:
            logger.warning("Could not load municipal candidates (%s).", exc)

    def search(self, query: str, limit: int = 15) -> SearchResultResponse:
        """Searches across municipalities and Senate districts."""
        self.initialize_defaults()
        clean_q = normalize_text(query)
        if not clean_q:
            return SearchResultResponse(query=query, total_found=0, results=[])

        matches: List[SearchResultItem] = []

        # Check if query is exact district number or code
        if clean_q.isdigit():
            q_num = int(clean_q)
            if q_num in self.senate_districts:
                matches.append(self.senate_districts[q_num])
            q_padded = clean_q.zfill(6)
            if q_padded in self.municipalities:
                matches.append(self.municipalities[q_padded])

        # Search Senate districts
        for num, item in self.senate_districts.items():
            if item in matches:
                continue
            if clean_q in normalize_text(item.name) or clean_q in normalize_text(item.description):
                matches.append(item)

        # Search municipalities
        for code, item in self.municipalities.items():
            if item in matches:
                continue
            norm_name = normalize_text(item.name)
            # Exact match gets first priority
            if clean_q == norm_name:
                matches.insert(0, item)
            elif clean_q in norm_name:
                matches.append(item)

        # Truncate to limit
        final_results = matches[:limit]
        return SearchResultResponse(
            query=query,
            total_found=len(matches),
            results=final_results,
        )

    def resolve_senate_district(self, identifier: str | int) -> Optional[int]:
        """Resolves an input (number or district city name) to a Senate district number."""
        self.initialize_defaults()
        s_id = str(identifier).strip()
        if s_id.isdigit():
            num = int(s_id)
            if num in self.senate_districts:
                return num
            return None

        clean_name = normalize_text(s_id)
        for num, item in self.senate_districts.items():
            if clean_name in normalize_text(item.name) or clean_name in normalize_text(item.description):
                return num

        return None

    def resolve_municipality_code(self, identifier: str) -> Optional[str]:
        """Resolves municipality name or code to the 6-digit KODZASTUP."""
        self.initialize_defaults()
        clean = identifier.strip()
        if clean.isdigit():
            padded = clean.zfill(6)
            if padded in self.municipalities:
                return padded
            return padded  # Return as-is if numeric code given

        norm = normalize_text(clean)
        for code, item in self.municipalities.items():
            if norm == normalize_text(item.name):
                return code

        # Partial match fallback
        for code, item in self.municipalities.items():
            if norm in normalize_text(item.name):
                return code

        return None


# Global singleton codebook index
codebook_index = CodebookIndex()
