"""The MCP endpoint as LiteLLM sees it: a user token is required, and the tools act for that user only. Tokens are
signed here with a test key."""

import time

import jwt
import pytest
import server
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from tests.fakes import FakeTable

TENANT = "00000000-0000-4000-8000-000000000001"
TRIPS_APP = "00000000-0000-4000-8000-000000000002"
GATEWAY_APP = "00000000-0000-4000-8000-000000000003"
ENV = {"TRIPS_AUTH_TENANT_ID": TENANT, "TRIPS_AUTH_AUDIENCE": f"api://{TRIPS_APP}"}
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def token(key=KEY, **overrides):
    now = int(time.time())
    claims = {
        "aud": TRIPS_APP,
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "iat": now,
        "exp": now + 600,
        "tid": TENANT,
        "oid": "alice",
        "azp": GATEWAY_APP,
        "scp": "Trips.ReadWrite",
        **overrides,
    }
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm="RS256")


@pytest.fixture
def client(monkeypatch):
    tables = {"trips": FakeTable(), "expenses": FakeTable()}
    monkeypatch.setattr(server, "table", lambda name: tables[name])
    app = server.create_app(ENV, signing_key_for=lambda _token: KEY.public_key())
    with TestClient(app) as test_client:
        yield test_client


def call_tool(client, name, arguments=None, bearer=None):
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }
    headers = {**HEADERS, "Authorization": f"Bearer {bearer or token()}"}
    return client.post("/mcp", json=message, headers=headers)


def test_health_needs_no_token(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_the_server_offers_two_read_tools_and_a_write_tool(client):
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

    response = client.post("/mcp", json=message, headers={**HEADERS, "Authorization": f"Bearer {token()}"})

    assert {tool["name"] for tool in response.json()["result"]["tools"]} == {"list_trips", "get_trip", "add_expense"}


def test_a_user_lists_their_trips_and_files_an_expense(client):
    listed = call_tool(client, "list_trips").json()["result"]
    filed = call_tool(
        client,
        "add_expense",
        {"trip_id": "TRIP-1001", "category": "meal", "amount": 220, "description": "Dinner", "attendees": 4},
    ).json()["result"]

    trip = call_tool(client, "get_trip", {"trip_id": "TRIP-1001"}).json()["result"]

    assert "Paris" in str(listed["structuredContent"])
    assert not filed.get("isError")
    assert trip["structuredContent"]["expenses_total"] == 220


def test_another_user_does_not_see_the_expense(client):
    call_tool(client, "list_trips")
    call_tool(client, "add_expense", {"trip_id": "TRIP-1001", "category": "meal", "amount": 50, "description": "Lunch"})

    bob = call_tool(client, "get_trip", {"trip_id": "TRIP-1001"}, bearer=token(oid="bob")).json()["result"]

    assert bob["isError"] is True


def test_invalid_arguments_return_a_tool_error(client):
    result = call_tool(client, "get_trip", {"trip_id": "nope"}).json()["result"]

    assert result["isError"] is True
    assert "TRIP-1001" in str(result["content"])


@pytest.mark.parametrize(
    "bearer",
    [
        "not-a-token",
        token(key=rsa.generate_private_key(public_exponent=65537, key_size=2048)),
        token(aud="api://another-app"),
        token(iss="https://login.microsoftonline.com/another-tenant/v2.0"),
        token(scp=None, roles=["Trips.ReadWrite"]),
        token(scp="User.Read"),
        token(exp=int(time.time()) - 60),
    ],
    ids=["garbage", "wrong-signature", "wrong-audience", "wrong-tenant", "app-only", "wrong-scope", "expired"],
)
def test_anything_but_a_valid_user_token_gets_401(client, bearer):
    assert call_tool(client, "list_trips", bearer=bearer).status_code == 401


def test_no_token_gets_401(client):
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

    assert client.post("/mcp", json=message, headers=HEADERS).status_code == 401
