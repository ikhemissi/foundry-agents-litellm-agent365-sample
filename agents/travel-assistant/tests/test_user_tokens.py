"""The forwarded user tokens: kept for the request, removed from what the hosting server sees, required for a POST."""

import pytest
import user_tokens
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

TOKENS = {"x-client-gateway-token": "Bearer gateway-token", "x-client-foundry-token": "foundry-token"}


async def echo(request: Request) -> JSONResponse:
    tokens = user_tokens.current.get()
    return JSONResponse(
        {
            "gateway": tokens.gateway if tokens else None,
            "foundry": tokens.foundry if tokens else None,
            "headers_seen": sorted(name for name in request.headers if name.startswith("x-client")),
        }
    )


@pytest.fixture
def client():
    app = Starlette(routes=[Route("/responses", echo, methods=["GET", "POST"])])
    app.add_middleware(user_tokens.ForwardedUserTokens)
    return TestClient(app)


def test_the_tokens_are_kept_for_the_request_and_removed_from_its_headers(client):
    seen = client.post("/responses", headers={**TOKENS, "x-client-request-id": "42"}).json()

    assert (seen["gateway"], seen["foundry"]) == ("gateway-token", "foundry-token")
    assert seen["headers_seen"] == ["x-client-request-id"]


@pytest.mark.parametrize("missing", ["x-client-gateway-token", "x-client-foundry-token"])
def test_a_post_without_both_tokens_is_refused(client, missing):
    headers = {name: value for name, value in TOKENS.items() if name != missing}

    response = client.post("/responses", headers=headers)

    assert response.status_code == 401
    assert "signed-in user" in response.json()["error"]


def test_other_requests_pass_without_tokens(client):
    assert client.get("/responses").status_code == 200


def test_the_tokens_are_never_printed():
    assert "token" not in repr(user_tokens.UserTokens(gateway="token", foundry="token")).replace("UserTokens", "")
