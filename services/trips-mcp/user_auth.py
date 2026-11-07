"""Every request to /mcp must carry a user's Entra access token for this server: issued in TRIPS_AUTH_TENANT_ID, for
TRIPS_AUTH_AUDIENCE (the server's app ID URI), with the delegated scope Trips.ReadWrite. Tokens without that scope,
such as app-only tokens, are refused: the tools act for a user. LiteLLM gets such a token On-Behalf-Of the user who
called it; the token's `azp` names the application that asked for it (the gateway), which the server logs.

Plain ASGI middleware rather than Starlette's BaseHTTPMiddleware, so that MCP's streamed responses pass untouched. The
user is handed to the tools in the request's state (`request.state.user`)."""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import jwt
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from trips import User

REQUIRED_SCOPE = "Trips.ReadWrite"
# Entra signs v1 and v2 tokens with the keys published here.
KEYS_URL = "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
logger = logging.getLogger("trips.auth")


@dataclass(frozen=True)
class UserPolicy:
    tenant_id: str
    audience: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "UserPolicy":
        return cls(tenant_id=env["TRIPS_AUTH_TENANT_ID"], audience=env["TRIPS_AUTH_AUDIENCE"])

    def user_from(self, token: str, signing_key: object) -> tuple[User, str]:
        """The user and the calling application, or jwt.InvalidTokenError unless it is a user token for this server."""
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
        if REQUIRED_SCOPE not in claims.get("scp", "").split():
            raise jwt.InvalidTokenError(f"not a user token with the {REQUIRED_SCOPE} scope")
        calling_app = claims.get("azp") or claims.get("appid", "")
        return User(tenant_id=claims["tid"], object_id=claims["oid"]), calling_app


class RequireUser:
    """Refuses requests to /mcp without a valid user token; /health stays open for the container's probe."""

    def __init__(self, app: ASGIApp, policy: UserPolicy, signing_key_for: Callable[[str], object] | None = None):
        self.app = app
        self.policy = policy
        keys = jwt.PyJWKClient(KEYS_URL.format(tenant=policy.tenant_id), cache_keys=True)
        self.signing_key_for = signing_key_for or (lambda token: keys.get_signing_key_from_jwt(token).key)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/mcp"):
            await self.app(scope, receive, send)
            return
        authorization = dict(scope["headers"]).get(b"authorization", b"").decode()
        scheme, _, token = authorization.partition(" ")
        try:
            if scheme.lower() != "bearer" or not token:
                raise jwt.InvalidTokenError("no bearer token")
            user, calling_app = self.policy.user_from(token, self.signing_key_for(token))
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as error:
            logger.info("refused: %s", error)
            response = JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
            await response(scope, receive, send)
            return
        scope.setdefault("state", {})["user"] = user
        scope["state"]["calling_app"] = calling_app
        await self.app(scope, receive, send)
