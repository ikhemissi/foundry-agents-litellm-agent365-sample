"""The MCP endpoint as LiteLLM sees it: list the tools, call them, and get readable errors."""

import pytest
import server
from starlette.testclient import TestClient

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
def client():
    with TestClient(server.create_app()) as test_client:
        yield test_client


def rpc(client, method, params=None):
    message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    response = client.post("/mcp", json=message, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_the_server_offers_two_read_tools(client):
    assert {tool["name"] for tool in rpc(client, "tools/list")["tools"]} == {"get_policy", "check_expense"}


def test_check_expense_returns_the_figures(client):
    arguments = {"category": "meal", "amount": 220, "count": 4, "with_customers": True}

    result = rpc(client, "tools/call", {"name": "check_expense", "arguments": arguments})

    assert result["structuredContent"]["limit"] == 360


def test_an_invalid_call_tells_the_model_why(client):
    result = rpc(client, "tools/call", {"name": "get_policy", "arguments": {"category": "gift"}})

    assert result["isError"] is True
    assert "category must be one of" in str(result["content"])
