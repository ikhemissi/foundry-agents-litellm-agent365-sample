"""Configures LiteLLM for the sample, through its admin API. Idempotent; reads the azd environment and uses your Azure
CLI sign-in (Key Vault Secrets Officer). Never prints a key. Run by the agents layer's postprovision hook, or:
    uv run python src/configure_gateway.py

- The MCP server Contoso_Trips (the name Agent 365 shows): LiteLLM exchanges the caller's token for the gateway app
  On-Behalf-Of the user (entra_obo) for a trips API token, and sends that to the trips MCP server.
- The A2A agent expense_policy_agent: the Foundry prompt agent's A2A 1.0 endpoint; LiteLLM forwards the caller's
  Authorization header (the user's Foundry token) to it.
- The Agent 365 guardrail (agent365), on for every MCP tool call: Agent 365 evaluates each call as the signed-in user,
  so every MCP call through LiteLLM must carry a user token (LiteLLM's open-source edition applies guardrails to all
  keys alike).
- One key per agent, in Key Vault, limited to what that agent uses:
  - travel-assistant: the model, Contoso_Trips and expense_policy_agent;
  - expense-policy: the model only.
- The proxy_admin user Agent 365 connects as, and its key (agent365-gateway-key).
"""

import os

from gateway_admin import Gateway, azd_values, read_secret, store_secret

TRIPS_SERVER = "Contoso_Trips"
POLICY_A2A_AGENT = "expense_policy_agent"
POLICY_FOUNDRY_AGENT = "expense-policy"
GUARDRAIL = "agent365"
AGENT365_USER = "agent365"
AGENT365_KEY_SECRET = "agent365-gateway-key"
TRAVEL_ASSISTANT_KEY_SECRET = "litellm-key-travel-assistant"
POLICY_AGENT_KEY_SECRET = "litellm-key-expense-policy"


def ensure_mcp_server(admin: Gateway, settings: dict) -> str:
    """Creates or updates an MCP server, found by name; returns its id."""
    name = settings["server_name"]
    existing = [server for server in admin.call("GET", "/v1/mcp/server") if server.get("server_name") == name]
    if existing:
        server_id = existing[0]["server_id"]
        admin.call("PUT", "/v1/mcp/server", {"server_id": server_id, **settings})
        print(f"MCP server '{name}' updated ({server_id})")
        return server_id
    server_id = admin.call("POST", "/v1/mcp/server", settings)["server_id"]
    print(f"MCP server '{name}' created ({server_id})")
    return server_id


def trips_server(values: dict, gateway_secret: str) -> dict:
    return {
        "server_name": TRIPS_SERVER,
        "alias": TRIPS_SERVER,
        "description": "Contoso's business trips: the signed-in user's trips, and the expenses filed for them.",
        "url": values["TRIPS_MCP_URL"],
        "transport": "http",
        "auth_type": "oauth2_token_exchange",
        "token_exchange_profile": "entra_obo",
        "token_exchange_endpoint": f"https://login.microsoftonline.com/{values['AZURE_TENANT_ID']}/oauth2/v2.0/token",
        "credentials": {
            "client_id": values["GATEWAY_CLIENT_ID"],
            "client_secret": gateway_secret,
            "scopes": [values["TRIPS_API_SCOPE"]],
        },
    }


def ensure_a2a_agent(admin: Gateway, values: dict) -> str:
    """Registers the expense policy agent's Foundry A2A endpoint (A2A 1.0, JSON-RPC); returns its LiteLLM id."""
    endpoint = f"{values['FOUNDRY_PROJECT_ENDPOINT']}/agents/{POLICY_FOUNDRY_AGENT}/endpoint/protocols/a2a"
    settings = {
        "agent_name": POLICY_A2A_AGENT,
        "agent_card_params": {
            "protocolVersion": "1.0",
            "name": POLICY_A2A_AGENT,
            "description": "Contoso's expense policy agent: answers questions about the travel expense policy.",
            "url": endpoint,
            "supportedInterfaces": [{"url": endpoint, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
            "version": "1.0.0",
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
            "capabilities": {"streaming": False},
            "skills": [
                {
                    "id": "expense-policy",
                    "name": "Expense policy",
                    "description": "Limits, approvals and receipts for travel expenses.",
                    "tags": ["expenses", "travel"],
                }
            ],
        },
        # The caller's Authorization header (the user's Foundry token) goes on to Foundry, which checks it.
        "extra_headers": ["authorization"],
    }
    existing = [agent for agent in admin.call("GET", "/v1/agents") if agent.get("agent_name") == POLICY_A2A_AGENT]
    if existing:
        agent_id = existing[0]["agent_id"]
        admin.call("PUT", f"/v1/agents/{agent_id}", settings)
        print(f"A2A agent '{POLICY_A2A_AGENT}' updated ({agent_id})")
        return agent_id
    agent_id = admin.call("POST", "/v1/agents", settings)["agent_id"]
    print(f"A2A agent '{POLICY_A2A_AGENT}' created ({agent_id})")
    return agent_id


def ensure_guardrail(admin: Gateway, values: dict, gateway_secret: str) -> None:
    """The Agent 365 guardrail, on for every MCP tool call (default_on); fail_closed blocks tool calls when Agent 365
    cannot be reached."""
    settings = {
        "guardrail_name": GUARDRAIL,
        "litellm_params": {
            "guardrail": "agent_365",
            "mode": "pre_mcp_call",
            "default_on": True,
            "tenant_id": values["AZURE_TENANT_ID"],
            "client_id": values["GATEWAY_CLIENT_ID"],
            "client_secret": gateway_secret,
            "unreachable_fallback": "fail_closed",
        },
        "guardrail_info": {"description": "Agent 365 evaluation of MCP tool calls, as the signed-in user."},
    }
    # /v2/guardrails/list includes the guardrails kept in the database (/guardrails/list does not).
    listed = admin.call("GET", "/v2/guardrails/list").get("guardrails", [])
    existing = [guardrail for guardrail in listed if guardrail.get("guardrail_name") == GUARDRAIL]
    if existing:
        admin.call("PUT", f"/guardrails/{existing[0]['guardrail_id']}", {"guardrail": settings})
        print(f"Guardrail '{GUARDRAIL}' updated")
        return
    admin.call("POST", "/guardrails", {"guardrail": settings})
    print(f"Guardrail '{GUARDRAIL}' created")


def ensure_agent_key(admin: Gateway, vault: str, secret_name: str, settings: dict) -> None:
    """An agent's key with exactly the given models, MCP servers and agents; kept in Key Vault."""
    key = read_secret(vault, secret_name)
    if key:
        admin.call("POST", "/key/update", {"key": key, **settings})
        print(f"Key '{settings['key_alias']}' updated")
        return
    key = admin.call("POST", "/key/generate", settings)["key"]
    store_secret(vault, secret_name, key)
    print(f"Key '{settings['key_alias']}' generated and stored in Key Vault ({secret_name})")


def ensure_agent365_key(admin: Gateway, vault: str) -> None:
    """The proxy_admin user Agent 365 acts as (blocking needs proxy_admin), and its key in Key Vault: revocable
    without touching the master key."""
    users = admin.call("GET", "/user/list")
    existing = users.get("users", []) if isinstance(users, dict) else users
    if not any(user.get("user_id") == AGENT365_USER for user in existing):
        user = {
            "user_id": AGENT365_USER,
            "user_alias": "Agent 365",
            "user_role": "proxy_admin",
            "auto_create_key": False,
        }
        admin.call("POST", "/user/new", user)
        print(f"LiteLLM user '{AGENT365_USER}' created (proxy_admin)")
    if read_secret(vault, AGENT365_KEY_SECRET):
        return
    generated = admin.call("POST", "/key/generate", {"user_id": AGENT365_USER, "key_alias": "agent365-gateway"})
    store_secret(vault, AGENT365_KEY_SECRET, generated["key"])
    print(f"Agent 365 key generated and stored in Key Vault ({AGENT365_KEY_SECRET})")


def main() -> None:
    values = {**azd_values(), **os.environ}
    vault = values["PLATFORM_KEY_VAULT_NAME"]
    admin_key = read_secret(vault, values["LITELLM_MASTER_KEY_SECRET_NAME"])
    gateway_secret = read_secret(vault, values["GATEWAY_SECRET_NAME"])
    if not admin_key or not gateway_secret:
        raise SystemExit("LiteLLM's admin key or the gateway app's secret is missing from Key Vault: provision first.")
    admin = Gateway(values["LITELLM_URL"], admin_key)
    model = values["FOUNDRY_MODEL_DEPLOYMENT_NAME"]

    trips_id = ensure_mcp_server(admin, trips_server(values, gateway_secret))
    policy_agent_id = ensure_a2a_agent(admin, values)
    ensure_guardrail(admin, values, gateway_secret)
    ensure_agent_key(
        admin,
        vault,
        TRAVEL_ASSISTANT_KEY_SECRET,
        {
            "key_alias": "travel-assistant",
            "models": [model],
            "object_permission": {"mcp_servers": [trips_id], "agents": [policy_agent_id]},
        },
    )
    ensure_agent_key(
        admin,
        vault,
        POLICY_AGENT_KEY_SECRET,
        {"key_alias": "expense-policy", "models": [model], "object_permission": {"mcp_servers": [], "agents": []}},
    )
    ensure_agent365_key(admin, vault)
    print(f"\nFor the Agent 365 admin center: gateway URL {values['LITELLM_URL']}")
    print(f"Key: az keyvault secret show --vault-name {vault} -n {AGENT365_KEY_SECRET} --query value -o tsv")


if __name__ == "__main__":
    main()
