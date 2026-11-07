"""Expense policy MCP server: Contoso's travel expense policy (get_policy) and a check of one expense against it
(check_expense), over streamable HTTP at /mcp, stateless, read-only. It holds no user data: it is reachable only inside
the Container Apps environment (internal ingress), through LiteLLM, which admits the expense policy agent with its own
key. The rules and limits are in policy.py."""

import logging
from typing import Any

import policy
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("expense_policy")
server = MCPServer(
    name="expense_policy",
    instructions="Contoso's travel expense policy. Quote the rules from get_policy and take every figure from "
    "check_expense: do not compute limits yourself.",
    version="1.0.0",
)


@server.tool(description="Get Contoso's travel expense rules for a category, with its limits in EUR.")
def get_policy(category: str, city: str | None = None) -> dict[str, Any]:
    """category: hotel, meal, transport or other. city: for hotels, the city of the stay."""
    found = policy.get_policy(category, city)
    logger.info("get_policy category=%s", category)
    return found


@server.tool(
    description="Check one expense against Contoso's policy: whether it is within the limit, the limit and how it "
    "was computed, and whether it needs manager approval or a receipt."
)
def check_expense(
    category: str,
    amount: float,
    currency: str = "EUR",
    city: str | None = None,
    count: int = 1,
    with_customers: bool = False,
) -> dict[str, Any]:
    """category: hotel, meal, transport or other. amount: the total. count: nights for a hotel, people for a meal.
    with_customers: whether customers or partners attended a meal."""
    arguments = {
        "category": category,
        "amount": amount,
        "currency": currency,
        "city": city,
        "count": count,
        "with_customers": with_customers,
    }
    checked = policy.check_expense(arguments)
    logger.info("check_expense category=%s within=%s", category, checked["within_policy"])
    return checked


@server.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_app():
    """The ASGI app serving /mcp and /health; a new one each call, since its session manager runs once per app."""
    return server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        # DNS-rebinding protection guards servers on localhost against browsers; this one runs behind Container Apps'
        # ingress, under a host name that depends on the environment.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
