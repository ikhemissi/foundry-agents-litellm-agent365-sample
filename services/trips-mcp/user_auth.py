"""Who may call the trips MCP server. A tool call acts for a user, so it must carry that user's Entra access token,
which LiteLLM passes on unchanged (oauth_delegate): the user's token for the AI gateway, issued in
TRIPS_AUTH_TENANT_ID, for TRIPS_AUTH_AUDIENCE (the gateway app's ID URI), with the delegated scope TRIPS_AUTH_SCOPE.
Tokens without that scope, such as app-only tokens, are refused. The token's `azp` names the application the user
signed in to, which the server logs.

Discovery needs no token: initialize, ping and tools/list (and the stream's GET and DELETE) describe the server and
its tools, not anyone's data, so that governance tools (Agent 365, through LiteLLM) can list the tools. A token that is
sent must still be valid.

Plain ASGI middleware rather than Starlette's BaseHTTPMiddleware, so that MCP's streamed responses pass untouched. The
user, when there is one, is handed to the tools in the request's state (`request.state.user`)."""

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import jwt
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from trips import User

# Entra signs v1 and v2 tokens with the keys published here.
KEYS_URL = "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
DISCOVERY_METHODS = {"initialize", "notifications/initialized", "ping", "tools/list"}
MAX_BODY_SIZE = 1_048_576
logger = logging.getLogger("trips.auth")


@dataclass(frozen=True)
class UserPolicy:
    tenant_id: str
    audience: str
    scope: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "UserPolicy":
        return cls(
            tenant_id=env["TRIPS_AUTH_TENANT_ID"], audience=env["TRIPS_AUTH_AUDIENCE"], scope=env["TRIPS_AUTH_SCOPE"]
        )

    def user_from(self, token: str, signing_key: object) -> tuple[User, str]:
        """The user and the application they signed in to, or jwt.InvalidTokenError unless it is a user token with
        the expected audience and scope."""
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            # v1 tokens name the app ID URI (api://<client id>), v2 tokens the client id alone.
            audience=[self.audience, self.audience.removeprefix("api://")],
            issuer=[
                f"https://sts.windows.net/{self.tenant_id}/",
                f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",
            ],
            options={"require": ["exp", "iat", "oid", "tid"]},
        )
        if self.scope not in claims.get("scp", "").split():
            raise jwt.InvalidTokenError(f"not a user token with the {self.scope} scope")
        calling_app = claims.get("azp") or claims.get("appid", "")
        return User(tenant_id=claims["tid"], object_id=claims["oid"]), calling_app


class RequireUser:
    """Lets discovery through without a token and refuses anything else without a valid user token (401); /health
    stays open for the container's probe."""

    def __init__(self, app: ASGIApp, policy: UserPolicy, signing_key_for: Callable[[str], object] | None = None):
        self.app = app
        self.policy = policy
        keys = jwt.PyJWKClient(KEYS_URL.format(tenant=policy.tenant_id), cache_keys=True)
        self.signing_key_for = signing_key_for or (lambda token: keys.get_signing_key_from_jwt(token).key)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/mcp"):
            await self.app(scope, receive, send)
            return
        body = await read_body(receive) if scope["method"] == "POST" else b""
        replay = replay_body(body, receive) if scope["method"] == "POST" else receive
        authorization = dict(scope["headers"]).get(b"authorization", b"").decode()
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            try:
                user, calling_app = self.policy.user_from(token, self.signing_key_for(token))
            except (jwt.InvalidTokenError, jwt.PyJWKClientError) as error:
                await refuse(scope, receive, send, f"invalid token: {error}")
                return
            scope.setdefault("state", {})["user"] = user
            scope["state"]["calling_app"] = calling_app
        elif not is_discovery(scope["method"], body):
            await refuse(scope, receive, send, "no bearer token")
            return
        await self.app(scope, replay, send)


def is_discovery(http_method: str, body: bytes) -> bool:
    """GET (the server's stream) and DELETE (closing a session) carry no data; a POST is discovery when every
    JSON-RPC message in it is one of DISCOVERY_METHODS."""
    if http_method in ("GET", "DELETE"):
        return True
    try:
        payload = json.loads(body)
    except ValueError:
        return False
    messages = payload if isinstance(payload, list) else [payload]
    return bool(messages) and all(
        isinstance(message, dict) and message.get("method") in DISCOVERY_METHODS for message in messages
    )


async def read_body(receive: Receive) -> bytes:
    """The request's body, read so that its JSON-RPC method can be checked; larger bodies are cut (and then refused
    as invalid JSON unless a valid token comes with them)."""
    chunks: list[bytes] = []
    size = 0
    more = True
    while more:
        message = await receive()
        chunk = message.get("body", b"")
        size += len(chunk)
        if size <= MAX_BODY_SIZE:
            chunks.append(chunk)
        more = message.get("more_body", False)
    return b"".join(chunks)


def replay_body(body: bytes, receive: Receive) -> Receive:
    """A receive callable that hands the body already read to the app, then the real receive (which reports the
    client's disconnect when it happens)."""
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


async def refuse(scope: Scope, receive: Receive, send: Send, reason: str) -> None:
    logger.info("refused: %s", reason)
    response = JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
    await response(scope, receive, send)
