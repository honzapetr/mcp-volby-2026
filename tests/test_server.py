import xml.etree.ElementTree as ET
import pytest
from starlette.testclient import TestClient

from src.client_csu import csu_client
from src.server import app, handle_call_tool, handle_list_tools
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



def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "mcp-volby-2026"


def test_api_search(client):
    response = client.get("/api/search?q=praha")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "praha"
    assert len(data["results"]) > 0
    assert any("Praha" in item["name"] for item in data["results"])


@pytest.mark.asyncio
async def test_mcp_list_tools():
    tools = await handle_list_tools()
    assert len(tools) >= 7
    tool_names = [t.name for t in tools]
    assert "get_election_overview" in tool_names
    assert "get_senate_results" in tool_names
    assert "get_municipal_results" in tool_names
    assert "search_municipality_or_district" in tool_names
    assert "get_live_counting_progress" in tool_names
    assert "get_senate_district_breakdown" in tool_names
    assert "get_coalition_scenarios" in tool_names


@pytest.mark.asyncio
async def test_mcp_call_search_tool():
    res = await handle_call_tool("search_municipality_or_district", {"query": "Brno"})
    assert len(res) == 1
    assert res[0].type == "text"
    assert "582786" in res[0].text
    assert "Brno" in res[0].text


@pytest.mark.asyncio
async def test_mcp_call_breakdown_and_coalition_tools():
    # Test breakdown tool
    res_b = await handle_call_tool("get_senate_district_breakdown", {"obvod": 3})
    assert len(res_b) == 1
    assert "Cheb" in res_b[0].text
    assert "municipalities" in res_b[0].text

    # Test coalition scenarios tool
    res_c = await handle_call_tool("get_coalition_scenarios", {"obec": "Praha"})
    assert len(res_c) == 1
    assert "Praha hl.m." in res_c[0].text
    assert "scenarios" in res_c[0].text
    assert "majority_seats" in res_c[0].text

    # Test municipal results tool with candidate response
    res_m = await handle_call_tool("get_municipal_results", {"obec": "Praha"})
    assert len(res_m) == 1
    assert "Praha hl.m." in res_m[0].text
    assert "parties" in res_m[0].text
    assert "elected_representatives" in res_m[0].text


@pytest.mark.asyncio
async def test_api_live_endpoints(client):
    # Test overview
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.json()
    assert "senate_summary" in data
    assert "municipal_summary" in data

    # Test senate all
    res_se = client.get("/api/senat")
    assert res_se.status_code == 200
    data_se = res_se.json()
    assert len(data_se["districts"]) == 2  # from MOCK_SENAT_XML (Cheb and Louny)

    # Test senate specific district (Cheb - 3)
    res_cheb = client.get("/api/senat/Cheb")
    assert res_cheb.status_code == 200
    data_cheb = res_cheb.json()
    assert len(data_cheb["districts"]) == 1
    assert data_cheb["districts"][0]["district_number"] == 3
    assert data_cheb["districts"][0]["lead_margin_votes"] == 4300

    # Test senate district breakdown by municipalities
    res_breakdown = client.get("/api/senat/Cheb/obce")
    assert res_breakdown.status_code == 200
    data_bd = res_breakdown.json()
    assert data_bd["district_number"] == 3
    assert data_bd["municipalities_total"] == 2

    # Test municipal for Praha (554782)
    res_praha = client.get("/api/obce/Praha")
    assert res_praha.status_code == 200
    data_praha = res_praha.json()
    assert data_praha["municipality_name"] == "Praha hl.m."
    assert data_praha["total_seats"] == 65
    assert data_praha["majority_seats"] == 33
    assert data_praha["winner"] == "Koalice A"
    assert data_praha["wasted_votes_pct"] == 3.00
    assert len(data_praha["parties"]) > 0
    assert "elected_representatives" in data_praha

    # Test coalition scenarios for Praha
    res_coalition = client.get("/api/obce/Praha/koalice")
    assert res_coalition.status_code == 200
    data_co = res_coalition.json()
    assert data_co["total_seats"] == 65
    assert data_co["majority_seats"] == 33
    assert len(data_co["scenarios"]) > 0
    # First scenario should be minimal winning coalition
    first_scen = data_co["scenarios"][0]
    assert first_scen["total_seats"] >= 33
    assert first_scen["is_minimal_winning"] is True

    # Test progress
    res_prog = client.get("/api/progress")
    assert res_prog.status_code == 200
    data_prog = res_prog.json()
    assert "status_message" in data_prog


def test_jsonrpc_initialize_and_tools(client):
    """Verifies that Streamable HTTP POST /sse and /mcp work for Antigravity IDE and modern clients."""
    # Test initialize
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "antigravity-ide", "version": "2.0"}
        }
    }
    res = client.post("/sse", json=init_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "serverInfo" in data["result"]
    assert data["result"]["serverInfo"]["name"] == "volby-cr-2026"
    assert "tools" in data["result"]["capabilities"]

    # Test tools/list on /mcp
    list_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    res_list = client.post("/mcp", json=list_payload)
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert data_list["id"] == 2
    tool_names = [t["name"] for t in data_list["result"]["tools"]]
    assert "get_election_overview" in tool_names
    assert "get_senate_results" in tool_names
    assert "get_senate_district_breakdown" in tool_names
    assert "get_coalition_scenarios" in tool_names
    assert "get_precinct_counting_speed" in tool_names


    # Test tools/call on /sse
    call_payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_municipality_or_district",
            "arguments": {"query": "Praha", "limit": 3}
        }
    }
    res_call = client.post("/sse", json=call_payload)
    assert res_call.status_code == 200
    data_call = res_call.json()
    assert data_call["id"] == 3
    assert data_call["result"]["isError"] is False
    assert len(data_call["result"]["content"]) >= 1
    assert "Praha" in data_call["result"]["content"][0]["text"]


def test_api_precinct_speed(client):
    """Verifies the /api/okrsky/rychlost endpoint for slowest and fastest ranking."""
    # Test slowest commissions
    res_slowest = client.get("/api/okrsky/rychlost?election_type=obce&order=slowest")
    assert res_slowest.status_code == 200
    data_slow = res_slowest.json()
    assert data_slow["order"] == "slowest"
    assert data_slow["election_type"] == "obce"
    assert len(data_slow["precincts"]) > 0
    # Okrsek 2 (18:30:00) should be first when ordered by slowest
    assert data_slow["precincts"][0]["precinct_number"] == 2
    assert "Nejpomalejší" in data_slow["summary_message"]

    # Test fastest commissions
    res_fastest = client.get("/api/okrsky/rychlost?election_type=obce&order=fastest")
    assert res_fastest.status_code == 200
    data_fast = res_fastest.json()
    assert data_fast["order"] == "fastest"
    # Okrsek 1 (14:45:00) should be first when ordered by fastest
    assert data_fast["precincts"][0]["precinct_number"] == 1
    assert "Nejrychlejší" in data_fast["summary_message"]

    # Test filtering by municipality and specific precinct number
    res_filt = client.get("/api/okrsky/rychlost?election_type=obce&obec=Praha&okrsek=1")
    assert res_filt.status_code == 200
    data_filt = res_filt.json()
    assert len(data_filt["precincts"]) == 1
    assert data_filt["precincts"][0]["precinct_number"] == 1
    assert data_filt["precincts"][0]["municipality_code"] == "554782"

    # Test Senate precinct filtering
    res_senat = client.get("/api/okrsky/rychlost?election_type=senat&obvod=3")
    assert res_senat.status_code == 200
    data_senat = res_senat.json()
    assert data_senat["election_type"] == "senat"
    assert len(data_senat["precincts"]) > 0
    assert all(p["district_number"] == 3 for p in data_senat["precincts"])


@pytest.mark.asyncio
async def test_mcp_call_precinct_speed_tool():
    """Verifies calling get_precinct_counting_speed via MCP tool interface."""
    res = await handle_call_tool(
        "get_precinct_counting_speed",
        {"election_type": "obce", "order": "slowest", "obec": "Praha", "limit": 5},
    )
    assert len(res) == 1
    text = res[0].text
    assert "554782" in text
    assert "slowest" in text
    assert "precincts" in text


