"""Global pytest fixtures and mocks for offline test stability."""

import asyncio
import xml.etree.ElementTree as ET
import pytest
from starlette.testclient import TestClient

from src.client_csu import csu_client
from src.server import app
from tests.test_parsers import (
    MOCK_KV_CR_XML,
    MOCK_MUNICIPAL_XML,
    MOCK_SENAT_XML,
    MOCK_SENATE_BREAKDOWN_XML,
)

MOCK_KV_OKRSKY_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY_OKRSKY xmlns="http://www.volby.cz/kv/" DATUM_CAS_GENEROVANI="2026-10-10T19:00:00">
  <OKRSEK CIS_OBEC="554782" CIS_OKRSEK="1" KODZASTUP="554782" PORADI_ZPRAC="1" DATUM_CAS_ZPRAC="2026-10-10T14:45:00" OPAKOVANE="0">
    <UCAST_OKRSEK ZAPSANI_VOLICI="800" VYDANE_OBALKY="400" PLATNE_HLASY="395" UCAST_PROC="50.00"/>
  </OKRSEK>
  <OKRSEK CIS_OBEC="554782" CIS_OKRSEK="2" KODZASTUP="554782" PORADI_ZPRAC="1" DATUM_CAS_ZPRAC="2026-10-10T18:30:00" OPAKOVANE="0">
    <UCAST_OKRSEK ZAPSANI_VOLICI="900" VYDANE_OBALKY="550" PLATNE_HLASY="540" UCAST_PROC="61.11"/>
  </OKRSEK>
  <OKRSEK CIS_OBEC="560715" CIS_OKRSEK="10" KODZASTUP="560715" PORADI_ZPRAC="1" DATUM_CAS_ZPRAC="2026-10-10T16:15:00" OPAKOVANE="0">
    <UCAST_OKRSEK ZAPSANI_VOLICI="300" VYDANE_OBALKY="150" PLATNE_HLASY="145" UCAST_PROC="50.00"/>
  </OKRSEK>
</VYSLEDKY_OKRSKY>
"""

MOCK_SENAT_OKRSKY_XML = """<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY_OKRSKY xmlns="http://www.volby.cz/senat/" DATUM_CAS_GENEROVANI="2026-10-10T19:00:00">
  <OKRSEK CIS_OBEC="560715" CIS_OKRSEK="1" CIS_OBVOD="3" PORADI_ZPRAC="1" DATUM_CAS_ZPRAC="2026-10-10T15:20:00" OPAKOVANE="0">
    <UCAST_OKRSEK ZAPSANI_VOLICI="600" VYDANE_OBALKY="200" PLATNE_HLASY="195" UCAST_PROC="33.33"/>
  </OKRSEK>
  <OKRSEK CIS_OBEC="560715" CIS_OKRSEK="2" CIS_OBVOD="3" PORADI_ZPRAC="1" DATUM_CAS_ZPRAC="2026-10-10T17:10:00" OPAKOVANE="0">
    <UCAST_OKRSEK ZAPSANI_VOLICI="700" VYDANE_OBALKY="250" PLATNE_HLASY="245" UCAST_PROC="35.71"/>
  </OKRSEK>
</VYSLEDKY_OKRSKY>
"""


@pytest.fixture
def client():
    """Provides a TestClient with an active asyncio event loop on Windows."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def mock_csu_calls(monkeypatch):
    """Mocks network calls to CSU to ensure reliable and fast offline tests."""
    async def mock_senat_vysledky():
        return ET.fromstring(MOCK_SENAT_XML)

    async def mock_kv_vysledky_cr():
        return ET.fromstring(MOCK_KV_CR_XML)

    async def mock_kv_obec(kod):
        return ET.fromstring(MOCK_MUNICIPAL_XML)

    async def mock_senat_obvod_obce(district_num):
        return ET.fromstring(MOCK_SENATE_BREAKDOWN_XML)

    async def mock_kv_okrsky(davka=None):
        return ET.fromstring(MOCK_KV_OKRSKY_XML)

    async def mock_senat_okrsky(davka=None):
        return ET.fromstring(MOCK_SENAT_OKRSKY_XML)

    monkeypatch.setattr(csu_client, "get_senat_vysledky", mock_senat_vysledky)
    monkeypatch.setattr(csu_client, "get_kv_vysledky_cr", mock_kv_vysledky_cr)
    monkeypatch.setattr(csu_client, "get_kv_obec", mock_kv_obec)
    monkeypatch.setattr(csu_client, "get_senat_obvod_obce", mock_senat_obvod_obce)
    monkeypatch.setattr(csu_client, "get_kv_okrsky", mock_kv_okrsky)
    monkeypatch.setattr(csu_client, "get_senat_okrsky", mock_senat_okrsky)
