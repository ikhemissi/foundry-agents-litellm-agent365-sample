"""Trips MCP server: the signed-in user's business trips (list_trips, get_trip) and a write tool (add_expense), over
streamable HTTP at /mcp, stateless, meant to be called through LiteLLM with a token for the user (user_auth.py). The
tool logic is in trips.py; trips and expenses are in Azure Tables reached with the app's managed identity
(AZURE_CLIENT_ID)."""

import logging
import os
from functools import cache
from typing import Any, Literal

import trips
from azure.data.tables import TableClient, TableServiceClient
from azure.identity import DefaultAzureCredential
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from user_auth import RequireUser, UserPolicy

logger = logging.getLogger("trips")
server = MCPServer(
    name="trips",
    instructions="Contoso's business travel: the signed-in user's trips and the expenses filed for them. "
    "Every tool acts for the signed-in user and sees only that user's trips.",
    version="1.0.0",
)


@cache
def table(name: str) -> TableClient:
    """A table of the storage account, created on first use."""
    service = TableServiceClient(endpoint=os.environ["TRIPS_TABLE_ENDPOINT"], credential=DefaultAzureCredential())
    return service.create_table_if_not_exists(name)


def signed_in(ctx: Context) -> trips.User:
    """The user RequireUser validated for this request, logged with the application that called for them."""
    state = ctx.request_context.request.state
    logger.info("user=%s via app=%s", state.user.object_id, state.calling_app)
    return state.user


@server.tool(description="List the signed-in user's business trips (upcoming and completed), soonest first.")
def list_trips(ctx: Context) -> list[dict[str, Any]]:
    found = trips.list_trips(table("trips"), signed_in(ctx))
    logger.info("list_trips count=%d", len(found))
    return found


@server.tool(description="Get one of the signed-in user's trips with the expenses already filed for it.")
def get_trip(ctx: Context, trip_id: str) -> dict[str, Any]:
    """trip_id: the trip's id from list_trips, e.g. TRIP-1001."""
    found = trips.get_trip(table("trips"), table("expenses"), signed_in(ctx), trip_id)
    logger.info("get_trip id=%s expenses=%d", trip_id, len(found["expenses"]))
    return found


@server.tool(
    description="File an expense on one of the signed-in user's trips. Check the expense policy first, and file only "
    "what the user asked to file."
)
def add_expense(
    ctx: Context,
    trip_id: str,
    category: Literal["hotel", "meal", "transport", "other"],
    amount: float,
    description: str,
    currency: str = "EUR",
    attendees: int = 1,
) -> dict[str, Any]:
    """trip_id: the trip's id from list_trips. category: a meal is "meal". amount: the total paid.
    description: what it was, at most 200 characters. attendees: how many people a meal was for."""
    arguments = {
        "trip_id": trip_id,
        "category": category,
        "amount": amount,
        "description": description,
        "currency": currency,
        "attendees": attendees,
    }
    filed = trips.add_expense(table("trips"), table("expenses"), signed_in(ctx), arguments)
    logger.info("add_expense id=%s trip=%s category=%s", filed["id"], trip_id, category)
    return filed


@server.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_app(env=os.environ, signing_key_for=None):
    """The ASGI app serving /mcp (users only) and /health; a new one each call, since its session manager runs once
    per app. uvicorn calls it (--factory), so that importing this module needs no settings."""
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        # DNS-rebinding protection guards servers on localhost against browsers; this one runs behind Container Apps'
        # ingress, under a host name that depends on the environment.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return RequireUser(app, UserPolicy.from_env(env), signing_key_for)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# The Azure SDK logs every storage request and response at INFO: keep the log to what the tools did.
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
