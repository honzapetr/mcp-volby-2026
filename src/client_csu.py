"""Asynchronous HTTP client for downloading and caching election data from CSU (volby.cz / volby.gov.cz).

Includes:
- Robust error handling and exponential retries
- In-memory TTL caching to respect CSU server limits and reduce latency
- Cookie persistence (cookiesession1)
- Thread-safe / async execution
"""

import asyncio
import io
import json
import logging
import time
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional, Tuple

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a cached value with expiration."""
    def __init__(self, data: Any, ttl_seconds: int):
        self.data = data
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CSUClient:
    """Client for retrieving real-time election data from CSU."""

    def __init__(self):
        self.base_url = settings.CSU_BASE_URL.rstrip("/")
        self.cache_ttl = settings.CACHE_TTL_SECONDS
        self.timeout = settings.HTTP_TIMEOUT_SECONDS
        self.max_retries = settings.HTTP_MAX_RETRIES
        self.headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "*/*",
        }
        self._cache: Dict[str, CacheEntry] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def get_client(self) -> httpx.AsyncClient:
        """Returns or initializes the httpx async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Closes the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _fetch_with_retry(self, url: str) -> bytes:
        """Executes GET request with exponential backoff retry."""
        client = await self.get_client()
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
            except (httpx.HTTPError, httpx.RequestError) as exc:
                last_error = exc
                wait_time = 0.5 * (2 ** (attempt - 1))
                logger.warning(
                    "Error fetching %s (attempt %d/%d): %s. Retrying in %.2fs",
                    url, attempt, self.max_retries, exc, wait_time
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait_time)

        logger.error("Failed to fetch %s after %d attempts: %s", url, self.max_retries, last_error)
        raise RuntimeError(f"Chyba při stahování dat z ČSÚ ({url}): {last_error}")

    async def get_xml(self, url: str, ttl: Optional[int] = None) -> ET.Element:
        """Fetches and parses XML document with caching."""
        effective_ttl = ttl if ttl is not None else self.cache_ttl
        cache_key = f"xml:{url}"

        async with self._lock:
            if cache_key in self._cache and not self._cache[cache_key].is_expired():
                return self._cache[cache_key].data

        content = await self._fetch_with_retry(url)
        try:
            # Strip potential UTF-8 BOM or whitespace
            root = ET.fromstring(content.strip())
        except ET.ParseError as exc:
            logger.error("XML parse error from %s: %s", url, exc)
            raise ValueError(f"Neplatný formát XML z {url}: {exc}")

        async with self._lock:
            self._cache[cache_key] = CacheEntry(root, effective_ttl)

        return root

    async def get_zip_json(self, url: str, json_filename: str, ttl: int = 3600) -> Any:
        """Downloads a zip archive and extracts a JSON file (used for codebooks)."""
        cache_key = f"json_zip:{url}:{json_filename}"

        async with self._lock:
            if cache_key in self._cache and not self._cache[cache_key].is_expired():
                return self._cache[cache_key].data

        content = await self._fetch_with_retry(url)
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                raw_json = zf.read(json_filename).decode("utf-8")
                parsed = json.loads(raw_json)
        except Exception as exc:
            logger.error("Failed to extract %s from %s: %s", json_filename, url, exc)
            raise ValueError(f"Chyba při čtení číselníku {json_filename}: {exc}")

        async with self._lock:
            self._cache[cache_key] = CacheEntry(parsed, ttl)

        return parsed

    # Higher-level election data methods

    async def get_senat_vysledky(self) -> ET.Element:
        """Returns overall Senate results (vysledky.xml)."""
        url = f"{self.base_url}/appdata/senat/{settings.SENAT_ELECTION_CODE}/odata/vysledky.xml"
        return await self.get_xml(url)

    async def get_senat_obvod_obce(self, district_num: int) -> ET.Element:
        """Returns municipality results within a specific Senate district."""
        url = f"{self.base_url}/appdata/senat/{settings.SENAT_ELECTION_CODE}/odata/obvody/vysledky_obce_obvod_{district_num}.xml"
        return await self.get_xml(url)

    async def get_kv_vysledky_cr(self) -> ET.Element:
        """Returns nationwide municipal election results."""
        url = f"{self.base_url}/appdata/{settings.KV_VERSION}/{settings.KV_ELECTION_CODE}/odata/vysledky.xml"
        return await self.get_xml(url)

    async def get_kv_obec(self, kod_zastup: str) -> ET.Element:
        """Returns municipal election results for a specific municipality (e.g. 554782 for Prague)."""
        # Ensure 6 digits
        kod_clean = str(kod_zastup).strip().zfill(6)
        url = f"{self.base_url}/appdata/{settings.KV_VERSION}/{settings.KV_ELECTION_CODE}/odata/zastup/vysledky_obec_{kod_clean}.xml"
        return await self.get_xml(url)

    async def get_kv_okres(self, nuts_code: str) -> ET.Element:
        """Returns municipal results for all towns in an administrative district (NUTS)."""
        nuts_clean = nuts_code.strip().upper()
        url = f"{self.base_url}/appdata/{settings.KV_VERSION}/{settings.KV_ELECTION_CODE}/odata/okresy/vysledky_obce_okres_{nuts_clean}.xml"
        return await self.get_xml(url)


# Global singleton client
csu_client = CSUClient()
