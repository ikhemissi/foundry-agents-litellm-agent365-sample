"""The signed-in user's tokens, which the caller (the chat UI) forwards to this hosted agent in two headers that Foundry
passes on to the container (`x-client-*`):
- x-client-gateway-token: for the AI gateway's app; LiteLLM exchanges it On-Behalf-Of the user for the trips MCP
  server and the Agent 365 guardrail;
- x-client-foundry-token: for Foundry (https://ai.azure.com); LiteLLM forwards it to the expense policy agent (A2A).

The middleware takes both headers out of the request before the hosting server sees it (so that they never reach the
request's metadata, logs or stored responses), keeps them for this request only, and refuses a request without them:
the agent never falls back to an identity of its own for what it does for the user. Plain ASGI middleware rather than
Starlette's BaseHTTPMiddleware, so that streamed responses pass untouched."""

import json
from contextvars import ContextVar
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

GATEWAY_HEADER = b"x-client-gateway-token"
FOUNDRY_HEADER = b"x-client-foundry-token"


@dataclass(frozen=True, repr=False)
class UserTokens:
    gateway: str
    foundry: str

    def __repr__(self) -> str:
        return "UserTokens(<redacted>)"


current: ContextVar[UserTokens | None] = ContextVar("user_tokens", default=None)


class ForwardedUserTokens:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # ASGI servers give header names in lower case.
        forwarded = {name: value for name, value in scope["headers"] if name in (GATEWAY_HEADER, FOUNDRY_HEADER)}
        clean_scope = {**scope, "headers": [(name, value) for name, value in scope["headers"] if name not in forwarded]}
        tokens = UserTokens(
            gateway=_bearer(forwarded.get(GATEWAY_HEADER, b"")), foundry=_bearer(forwarded.get(FOUNDRY_HEADER, b""))
        )
        if scope["method"] == "POST" and not (tokens.gateway and tokens.foundry):
            await _refuse(send)
            return
        reset = current.set(tokens)
        try:
            await self.app(clean_scope, receive, send)
        finally:
            current.reset(reset)


def _bearer(value: bytes) -> str:
    """The token in a header, with or without the "Bearer " prefix; empty when there is none."""
    text = value.decode("ascii", errors="ignore").strip()
    return text.removeprefix("Bearer ").strip()


async def _refuse(send: Send) -> None:
    body = json.dumps({"error": "This agent acts for the signed-in user: forward the user's tokens."}).encode()
    await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})
