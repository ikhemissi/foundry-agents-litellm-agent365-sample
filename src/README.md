# Scripts

Run from the repository root with `uv run python src/<script>.py`. They read the azd environment (`azd env get-values`) and use your Azure CLI sign-in; none prints a key.

| Script | What it does | When |
|---|---|---|
| `configure_gateway.py` | Configures LiteLLM through its admin API: the trips MCP server (the user's token passed on: `oauth_delegate`), the A2A agent, the Agent 365 guardrail, one key per agent, the key Agent 365 connects with | The postprovision hook ([infra/hooks/postprovision](../infra/hooks/postprovision)); again after changing it |
| `deploy_policy_agent.py` | Deploys the expense policy agent (prompt agent): its model connection, its skill (instructions and code), its A2A endpoint | Same hook, after `configure_gateway.py` |
| `ask_travel_assistant.py` | Asks the travel assistant a question as you, without the chat UI, and lists the tool calls it made | Any time: `uv run python src/ask_travel_assistant.py "What are my upcoming trips?"` |
| `gateway_admin.py` | Shared helpers: azd values, Key Vault, LiteLLM's admin API | — |
