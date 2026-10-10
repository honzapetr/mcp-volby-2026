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
from typing import Dict, List, Optional, Tuple

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
    ("555134", "Ostrava", "CZ0806", "Statutární město Ostrava (Moravskoslezský kraj)"),
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
    ("538523", "Kolín", "CZ0204", "Město Kolín (Středočeský kraj)"),
    ("533165", "Kutná Hora", "CZ0205", "Město Kutná Hora (Středočeský kraj)"),
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
    ("593711", "Vyškov", "CZ0646", "Město Vyškov (Jihomoravský kraj)"),
    ("593711", "Znojmo", "CZ0647", "Město Znojmo (Jihomoravský kraj)"),
    ("535419", "Jeseník", "CZ0711", "Město Jeseník (Olomoucký kraj)"),
    ("538523", "Šumperk", "CZ0715", "Město Šumperk (Olomoucký kraj)"),
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

    async def load_remote_codebooks(self):
        """Optionally loads complete nationwide municipality list from CSU open data."""
        try:
            self.initialize_defaults()
            url = f"{settings.CSU_BASE_URL}/opendata/{settings.KV_VERSION}/KV2026ciselniky20261007_json.zip"
            data = await csu_client.get_zip_json(url, "kvcoco.json", ttl=86400)
            items = data.get("položky", []) if isinstance(data, dict) else []
            count_added = 0
            for item in items:
                kod = str(item.get("KODZASTUP", item.get("kód", ""))).strip().zfill(6)
                nazev = item.get("NAZEVZAST", "")
                if not nazev and isinstance(item.get("název"), dict):
                    nazev = item["název"].get("cs", "")
                nuts = str(item.get("NUTS", ""))

                if kod and nazev:
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
            if 1 <= num <= 81:
                return num

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
