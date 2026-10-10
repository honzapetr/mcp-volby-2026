"""Integration tests for FastAPI application and MCP tools."""

import pytest
from starlette.testclient import TestClient

from src.server import app, handle_call_tool, handle_list_tools


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


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
    assert len(tools) >= 5
    tool_names = [t.name for t in tools]
    assert "get_election_overview" in tool_names
    assert "get_senate_results" in tool_names
    assert "get_municipal_results" in tool_names
    assert "search_municipality_or_district" in tool_names
    assert "get_live_counting_progress" in tool_names


@pytest.mark.asyncio
async def test_mcp_call_search_tool():
    res = await handle_call_tool("search_municipality_or_district", {"query": "Brno"})
    assert len(res) == 1
    assert res[0].type == "text"
    assert "582786" in res[0].text
    assert "Brno" in res[0].text


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
    assert data_se["districts_total"] >= 27

    # Test senate specific district (Cheb - 3)
    res_cheb = client.get("/api/senat/Cheb")
    assert res_cheb.status_code == 200
    data_cheb = res_cheb.json()
    assert len(data_cheb["districts"]) == 1
    assert data_cheb["districts"][0]["district_number"] == 3

    # Test municipal for Praha (554782)
    res_praha = client.get("/api/obce/Praha")
    assert res_praha.status_code == 200
    data_praha = res_praha.json()
    assert data_praha["municipality_name"] == "Praha hl.m."
    assert data_praha["total_seats"] == 65
    assert len(data_praha["parties"]) > 0

    # Test progress
    res_prog = client.get("/api/progress")
    assert res_prog.status_code == 200
    data_prog = res_prog.json()
    assert "status_message" in data_prog

