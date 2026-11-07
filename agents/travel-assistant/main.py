"""Contoso's travel assistant: a Foundry hosted agent (Agent Framework, Responses protocol) that acts for the signed-in
user. For each request it builds an agent with:
- the trips MCP server through LiteLLM, with the user's gateway token (LiteLLM exchanges it for the trips API);
- ask_expense_policy: the expense policy agent over A2A 1.0 through LiteLLM, with the user's Foundry token;
- the model through LiteLLM, with this agent's own LiteLLM key (read from Key Vault with the agent's identity).
The user's tokens come from the caller in forwarded headers (user_tokens.py); without them the request is refused."""

import asyncio
import logging
import os
from functools import cache
from typing import Any, Self

import a2a
import httpx
import user_tokens
from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.observability import enable_instrumentation
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework_foundry_hosting import HostedResponseRequest, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.monitor.opentelemetry import configure_azure_monitor
from openai import AsyncOpenAI

INSTRUCTIONS = """You are Contoso's travel assistant, working for the signed-in employee.
- Use the trips tools to read the user's trips and to file expenses on them.
- For anything the expense policy decides (limits, approvals, receipts), call ask_expense_policy with the facts: the
  category, the city, the amount in EUR, the number of nights or people, and whether customers attended. Never state a
  limit or a rule yourself: quote what the expense policy agent answered.
- File an expense only when the user asks you to, after checking it against the policy; then say what you filed.
- If a tool says how to fix your call (an invalid argument), fix it and try once more.
- If a tool is refused or unavailable, tell the user plainly; do not guess its result."""
logger = logging.getLogger("travel_assistant")


@cache
def settings() -> dict[str, str]:
    names = (
        "LITELLM_URL",
        "KEY_VAULT_URI",
        "LITELLM_KEY_SECRET_NAME",
        "MODEL",
        "TRIPS_MCP_SERVER",
        "EXPENSE_POLICY_A2A_AGENT",
    )
    return {name: os.environ[name] for name in names}


@cache
def credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


_gateway_key: str | None = None


async def gateway_key() -> str:
    """This agent's LiteLLM key, read on the first request and kept: the agent's identity gets its Key Vault role
    after the agent is deployed (the service's postdeploy hook), so reading it at start-up could fail."""
    global _gateway_key
    if _gateway_key is None:
        vault = SecretClient(settings()["KEY_VAULT_URI"], credential())
        secret = await asyncio.to_thread(vault.get_secret, settings()["LITELLM_KEY_SECRET_NAME"])
        _gateway_key = secret.value
    return _gateway_key


class GatewayChatClient(OpenAIChatCompletionClient):
    """The model through LiteLLM's OpenAI-compatible API. The hosting server enters the agent for each request, and
    the agent enters its client: close the HTTP client when the request ends."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.client.close()


def gateway_headers(key: str, user_token: str) -> dict[str, str]:
    """LiteLLM admits the call with this agent's key; the user's token is what it passes on (or exchanges)."""
    return {"x-litellm-api-key": key, "Authorization": f"Bearer {user_token}"}


def trips_tool(tokens: user_tokens.UserTokens, key: str) -> MCPStreamableHTTPTool:
    return MCPStreamableHTTPTool(
        name="trips",
        url=f"{settings()['LITELLM_URL']}/mcp/{settings()['TRIPS_MCP_SERVER']}",
        static_headers=gateway_headers(key, tokens.gateway),
        load_prompts=False,
    )


def expense_policy_tool(tokens: user_tokens.UserTokens, key: str) -> Any:
    url = f"{settings()['LITELLM_URL']}/a2a/{settings()['EXPENSE_POLICY_A2A_AGENT']}"
    headers = gateway_headers(key, tokens.foundry)

    @tool(name="ask_expense_policy", description="Ask Contoso's expense policy agent a question (A2A 1.0).")
    async def ask_expense_policy(question: str) -> str:
        """question: the question, with every fact the policy needs (category, city, amount in EUR, nights or
        people, whether customers attended)."""
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            return await a2a.send_message(client, url, question, headers)

    return ask_expense_policy


async def create_agent() -> Agent:
    """A new agent for each request, bound to that request's user (see the module's docstring)."""
    tokens = user_tokens.current.get()
    if tokens is None:
        raise PermissionError("No user tokens for this request.")
    key = await gateway_key()
    model = GatewayChatClient(
        model=settings()["MODEL"],
        async_client=AsyncOpenAI(base_url=f"{settings()['LITELLM_URL']}/v1", api_key=key, max_retries=0),
    )
    return Agent(
        client=model,
        name="travel-assistant",
        instructions=INSTRUCTIONS,
        tools=[trips_tool(tokens, key), expense_policy_tool(tokens, key)],
    )


def prepare_options(request: HostedResponseRequest, options: dict[str, Any]) -> dict[str, Any]:
    """The model is called through Chat Completions, which has no Responses `include` projections; and the user's
    tokens live only as long as the request, so background runs are refused."""
    if request.request.get("background"):
        raise ValueError("This agent acts for the signed-in user and runs only in the foreground of their request.")
    if options.pop("include", None) is not None:
        logger.warning("Dropped the Responses option include, which Chat Completions does not support.")
    return options


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # Application Insights accepts only Entra-authenticated telemetry: the agent's identity has the publisher role.
    configure_azure_monitor(
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"], credential=credential()
    )
    # Spans for the agent, its model calls and tool calls, without message content.
    enable_instrumentation(enable_sensitive_data=False, enable_message_events=False)
    # The exporter is configured above, with the agent's identity: the server must not configure a second one.
    server = ResponsesHostServer(create_agent, prepare_options=prepare_options, configure_observability=None)
    server.add_middleware(user_tokens.ForwardedUserTokens)
    server.run()


if __name__ == "__main__":
    main()
