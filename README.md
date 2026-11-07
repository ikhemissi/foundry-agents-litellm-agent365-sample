# Foundry agents with LiteLLM, governed by Agent 365

![Foundry agents with LiteLLM, governed by Agent 365: a chat talks to a Foundry hosted agent acting as the user, which reaches an MCP server and, over A2A 1.0, a Foundry prompt agent through a LiteLLM gateway that Agent 365 governs](docs/overview.svg)

A working sample of two **Microsoft Foundry** agents that work together through a **LiteLLM** gateway, using open protocols end to end, with **Microsoft Agent 365** governing the tools:

- a **hosted agent** (Microsoft Agent Framework, Responses protocol) that acts **as the signed-in user**;
- a **prompt agent** reached over **A2A 1.0**, whose policy is a skill in the open **Agent Skills** format, computed by code in the **code interpreter**;
- models, an **MCP** server and the A2A agent, all **through LiteLLM**, with one key per agent;
- **Agent 365** discovers the MCP tools LiteLLM exposes, blocks and unblocks them, and evaluates every tool call as the user;
- a **CopilotKit** chat (**AG-UI**), **OpenTelemetry** to Application Insights, and infrastructure as **Terraform** layers deployed with **azd**.

The scenario is fictional: Contoso's **travel assistant** reads an employee's trips and files their expenses, after asking Contoso's **expense policy agent** whether each expense fits the policy.

## What you'll see

> **You:** I'm in Paris next week. Is my hotel within the policy, and can I expense a €220 dinner for 4 with the customer?
>
> **Travel assistant:** Your Paris hotel is within policy: €210 per night is below the €230-per-night limit. The €220 dinner for 4 with a customer is also within policy: the limit is €360 (4 × €90). No manager approval is needed; keep the receipts.
>
> *Tool calls shown under the answer:* `Contoso_Trips-list_trips` (as you, through LiteLLM), `ask_expense_policy` twice (A2A 1.0, as you, through LiteLLM).

Then *"Please file the dinner"* files it on your trip with `Contoso_Trips-add_expense`. An administrator who blocks `add_expense` in Agent 365 stops that call at the gateway within seconds, and unblocking it restores it ([Govern with Agent 365](docs/agent365.md)).

## Architecture

```mermaid
flowchart LR
    user(["Employee"]) -->|"sign-in (MSAL)"| ui["Chat UI<br/>CopilotKit · AG-UI"]
    ui -->|"Responses, as the user<br/>+ the user's gateway and Foundry tokens"| assistant["Travel assistant<br/>Foundry hosted agent"]
    subgraph gateway["LiteLLM gateway"]
        mcp["MCP: Contoso_Trips"]
        a2a["A2A: expense_policy_agent"]
        models["Models"]
    end
    assistant -->|"MCP, as the user"| mcp
    assistant -->|"A2A 1.0, as the user"| a2a
    assistant -->|"model, own key"| models
    mcp -->|"the user's token, passed on"| trips["Trips MCP server"]
    a2a -->|"the user's Foundry token"| policy["Expense policy agent<br/>Foundry prompt agent<br/>skill + code interpreter"]
    policy -->|"model, own key"| models
    models -->|"managed identity"| model["Foundry model"]
    agent365["Agent 365"] -. "discovers, blocks, evaluates MCP tool calls" .-> mcp
```

### Who acts on each call

| Call | Credential | What the callee sees |
|---|---|---|
| Chat UI → travel assistant | The user's Foundry token, plus the user's gateway and Foundry tokens in `x-client-*` headers, which Foundry passes on to the agent | The signed-in user |
| Travel assistant → LiteLLM → trips MCP server | The agent's LiteLLM key admits the call; LiteLLM passes the user's gateway token on unchanged (`oauth_delegate`) | The user (`oid`), signed in to the chat (`azp`) |
| Travel assistant → LiteLLM → expense policy agent (A2A 1.0) | The agent's LiteLLM key; the user's Foundry token, which LiteLLM passes on | The user (Foundry Agent Consumer role) |
| Travel assistant → LiteLLM → model | The travel assistant's own LiteLLM key | The travel assistant |
| Expense policy agent → LiteLLM → model | The expense policy agent's own LiteLLM key, held in a project connection | The expense policy agent |
| LiteLLM → Foundry model | LiteLLM's managed identity | LiteLLM |
| LiteLLM → Agent 365 (guardrail) | LiteLLM exchanges the user's gateway token On-Behalf-Of the user | The user |

The travel assistant refuses any request that does not carry the user's tokens (HTTP 401): it never falls back to an identity of its own for what it does for the user. LiteLLM's spend logs attribute each call to the key that made it (`travel-assistant`, `expense-policy`).

## What runs where

| Path | What it is |
|---|---|
| [agents/travel-assistant](agents/travel-assistant) | The hosted agent (Python, Agent Framework): builds its tools for each request from the user's tokens ([main.py](agents/travel-assistant/main.py), [user_tokens.py](agents/travel-assistant/user_tokens.py), [a2a.py](agents/travel-assistant/a2a.py)) |
| [agents/expense-policy](agents/expense-policy) | The prompt agent: its role ([agent.json](agents/expense-policy/agent.json)) and its skill ([skill/SKILL.md](agents/expense-policy/skill/SKILL.md), [skill/scripts/policy.py](agents/expense-policy/skill/scripts/policy.py)) |
| [services/trips-mcp](services/trips-mcp) | The trips MCP server: each user's fictional trips and expenses; every tool call needs the user's token |
| [services/chat-ui](services/chat-ui) | The chat (Next.js, CopilotKit, MSAL), in its Foundry mode |
| [src](src) | LiteLLM configuration, the expense policy agent's deployment, a command-line client ([src/README.md](src/README.md)) |
| [infra](infra) | One Terraform root per azd layer, in the order of [azure.yaml](azure.yaml); each layer's notes are at the top of its `main.tf` |

## Deploy

You need an Azure subscription, the rights to create app registrations and grant tenant-wide admin consent (Global Administrator or Privileged Role Administrator), the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), [azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.37 or later with the Foundry extensions 1.0 or later, Terraform 1.9 or later, [uv](https://docs.astral.sh/uv/), and Node.js 22 for local checks of the chat UI. Agent 365 must be available in your tenant for the governance part.

```bash
az login && azd auth login
azd extension install azure.ai.agents azure.ai.projects   # or: azd extension upgrade …
azd env new <name> --location francecentral
azd env set RESOURCE_TAGS "key=value"            # optional: tags your organisation's policies require
azd hooks run preprovision                       # remote Terraform state, model quota check
azd provision <layer> --preview                  # for each layer in azure.yaml: read the plan before applying
azd up
```

`azd up` provisions the layers, then deploys the services. Along the way:

- the `agents` layer's hook configures LiteLLM and deploys the expense policy agent ([src](src));
- the travel assistant's postdeploy hook gives its identity read access to its own LiteLLM key and the right to publish telemetry;
- the chat-ui layer's hook pre-authorizes the chat on the gateway app.

Open the chat: `azd env get-value CHAT_UI_URL`. Only the user who deployed is allowed in (the chat layer's `ALLOWED_USER_OBJECT_IDS`), with the Foundry Agent Consumer role on the project (given by the `agents` layer).

Without the chat:

```bash
uv run python src/ask_travel_assistant.py "What are my upcoming trips?"
```

## Govern with Agent 365

Connect LiteLLM to Agent 365, then block and unblock tools: see [docs/agent365.md](docs/agent365.md).

## Observe

- **Application Insights** receives OpenTelemetry from the chat, the travel assistant and LiteLLM. Each Agent 365 evaluation is a `guardrail` dependency with its verdict, for example `{"verdict": "Allow", "defender_status": "Evaluated"}`.
- **LiteLLM's spend logs** (`/ui`, user `admin`, the admin key in Key Vault as `litellm-master-key`) show each call by key alias, model, MCP tool and A2A agent.
- **The trips MCP server's log** shows, for each call, the user and the application that called on their behalf.

## Design notes

- **Two kinds of agents, two roles.** The travel assistant is code (a hosted agent), so it can bind each request to the user's tokens and build its tools per request. The expense policy agent is configuration (a prompt agent): instructions, a model, the code interpreter. Prompt agents are the A2A targets in Foundry, so the expense policy agent is the one reached over A2A.
- **Figures come from code.** The policy's limits and checks are in [policy.py](agents/expense-policy/skill/scripts/policy.py) (tested), which the expense policy agent runs in the code interpreter for every answer. The skill folder follows the open Agent Skills format, so it can also be published as a Foundry skill.
- **One key per agent.** Each agent's LiteLLM key allows exactly the models, MCP servers and A2A agents it uses, and names it in LiteLLM's logs.
- **A user token on every MCP call.** The Agent 365 guardrail evaluates each MCP tool call as the user, and LiteLLM's open-source edition applies guardrails to every key alike. So every MCP call through LiteLLM carries a user token, and the expense policy agent, which acts as itself, calls no MCP server.
- **The user's token reaches the trips server.** LiteLLM passes the user's gateway token on unchanged (`oauth_delegate`), and the trips server checks it (tenant, the gateway app's audience, the `Tools.Use` scope) before any tool runs. Discovery (`initialize`, `tools/list`) needs no token, so that Agent 365 can list the tools with its own key; tool definitions hold no user data. LiteLLM's On-Behalf-Of exchange (`oauth2_token_exchange`) would give the trips server a token of its own audience, but it then needs a user token for discovery as well, which Agent 365 does not send.
- **A single client secret.** The Agent 365 guardrail's On-Behalf-Of exchange uses the gateway app's client secret, kept in Key Vault (and in LiteLLM's database). Everything else is passwordless: managed identities and the users' own tokens.

Versions used (November 2026): LiteLLM v1.106.6, Microsoft Agent Framework 1.22, MCP Python SDK 2.3, CopilotKit 1.79, azd 1.37 with the Foundry extensions 1.0, model `gpt-6-luna`.

## Clean up

```bash
azd down --purge
```

It deletes the resource group and purges the Key Vault and the Foundry account. The app registrations created by the `entra-apps` and `chat-ui` layers are deleted with their layers. Remove the LiteLLM gateway from Agent 365 (Gateways) too.

## License

[MIT](LICENSE)
