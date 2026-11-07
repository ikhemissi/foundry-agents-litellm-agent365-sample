"""The per-request agent: bound to the request's user, its key and its tools; and the options it refuses or drops."""

from types import SimpleNamespace

import main
import pytest
import user_tokens

SETTINGS = {
    "LITELLM_URL": "https://gateway.example",
    "KEY_VAULT_URI": "https://vault.example",
    "LITELLM_KEY_SECRET_NAME": "litellm-key-travel-assistant",
    "MODEL": "chat-model",
    "TRIPS_MCP_SERVER": "Contoso_Trips",
    "EXPENSE_POLICY_A2A_AGENT": "expense-policy",
}


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    monkeypatch.setattr(main, "settings", lambda: SETTINGS)

    async def agent_key():
        return "sk-agent"

    monkeypatch.setattr(main, "gateway_key", agent_key)


async def test_without_user_tokens_no_agent_is_built():
    with pytest.raises(PermissionError):
        await main.create_agent()


async def test_the_agent_gets_the_trips_mcp_server_and_the_expense_policy_agent_as_tools():
    reset = user_tokens.current.set(user_tokens.UserTokens(gateway="user-gateway", foundry="user-foundry"))
    try:
        agent = await main.create_agent()
    finally:
        user_tokens.current.reset(reset)

    assert [tool.url for tool in agent.mcp_tools] == ["https://gateway.example/mcp/Contoso_Trips"]
    assert "ask_expense_policy" in [getattr(tool, "name", "") for tool in agent.default_options["tools"]]


def test_litellm_admits_the_agent_by_its_key_and_gets_the_users_token():
    headers = main.gateway_headers("sk-agent", "user-gateway")

    assert headers == {"x-litellm-api-key": "sk-agent", "Authorization": "Bearer user-gateway"}


def test_background_runs_are_refused():
    request = SimpleNamespace(request={"background": True})

    with pytest.raises(ValueError, match="foreground"):
        main.prepare_options(request, {})


def test_the_include_option_is_dropped():
    request = SimpleNamespace(request={})

    assert main.prepare_options(request, {"include": ["reasoning"], "temperature": 0.2}) == {"temperature": 0.2}
