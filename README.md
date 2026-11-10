<div align="center">

# Foundry agents with LiteLLM, governed by Agent 365

**Two Microsoft Foundry agents that act as the signed-in user over MCP and A2A 1.0, through a LiteLLM gateway, with the tools governed by Microsoft Agent 365. Deployed with one `azd up`.**

[![CI](https://github.com/ikhemissi/foundry-agents-litellm-agent365-sample/actions/workflows/ci.yml/badge.svg)](https://github.com/ikhemissi/foundry-agents-litellm-agent365-sample/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)
[![IaC: Terraform](https://img.shields.io/badge/IaC-Terraform-623CE4?style=flat-square&logo=terraform)](infra)
[![Deploy: azd](https://img.shields.io/badge/deploy-azd-0078D4?style=flat-square)](azure.yaml)
[![Protocol: MCP](https://img.shields.io/badge/protocol-MCP-555555?style=flat-square)](services/trips-mcp)
[![Protocol: A2A 1.0](https://img.shields.io/badge/protocol-A2A%201.0-555555?style=flat-square)](agents/expense-policy)

[**Quick start**](#quick-start) · [**Architecture**](#architecture) · [**Who acts on each call**](#who-acts-on-each-call) · [**Cost**](#cost) · [**Documentation**](#documentation)

</div>

![Foundry agents with LiteLLM, governed by Agent 365: a chat talks to a Foundry hosted agent acting as the user, which reaches an MCP server and, over A2A 1.0, a Foundry prompt agent through a LiteLLM gateway that Agent 365 governs](docs/overview.svg)

## Why this sample

Agents become useful when they act for a person: they read that person's data, file their expenses, and ask other agents on their behalf. Every such call raises three questions: whose identity does it carry, which gateway sees it, and who can stop a tool that should not run. This sample answers them with open protocols and one gateway. The user's own tokens travel on every hop, every model, MCP and A2A call goes through LiteLLM, and Agent 365 governs the tools from one place.

## What it shows

A working sample of two **Microsoft Foundry** agents that work together through a **LiteLLM** gateway, using open protocols end to end, with **Microsoft Agent 365** governing the tools:

- a **hosted agent** (Microsoft Agent Framework, Responses protocol) that acts **as the signed-in user**;
- a **prompt agent** reached over **A2A 1.0**, whose policy is a skill in the open **Agent Skills** format, computed by code in the **code interpreter**;
- models, an **MCP** server and the A2A agent, all **through LiteLLM**, with one key per agent;
- **Agent 365** discovers the MCP tools LiteLLM exposes, blocks and unblocks them, and evaluates every tool call as the user;
- a **CopilotKit** chat (**AG-UI**), **OpenTelemetry** to Application Insights, and infrastructure as one **Terraform** root, built from small reusable modules and deployed with **azd**.

The scenario is fictional: Contoso's **travel assistant** reads an employee's trips and files their expenses, after asking Contoso's **expense policy agent** whether each expense fits the policy.

## What you'll see

> **You:** I'm in Paris next week. Is my hotel within the policy, and can I expense a €220 dinner for 4 with the customer?
>
> **Travel assistant** (abridged): Your Paris hotel is within policy: €210 per night is below the €230-per-night limit. The €220 dinner for 4 with a customer is also within policy: the limit is €360 (4 × €90). No manager approval is needed; keep the receipts.
>
> *Tool calls shown under the answer:* `Contoso_Trips-list_trips` (as you, through LiteLLM), `ask_expense_policy` twice (A2A 1.0, as you, through LiteLLM).

Then *"Please file the dinner"* files it on your trip with `Contoso_Trips-add_expense`. When an administrator blocks `add_expense` in Agent 365, the gateway stops offering it within seconds: the assistant still checks the policy but can no longer file expenses, until the tool is unblocked ([Govern with Agent 365](docs/agent365.md)).

| Filing an expense | A similar request, with `add_expense` blocked in Agent 365 |
|---|---|
| ![The chat: the user asks to file a 20 EUR taxi on their Paris trip; the tool calls Contoso_Trips-list_trips, ask_expense_policy and Contoso_Trips-add_expense are shown as done, and the assistant confirms the expense is filed and within policy](docs/chat.png) | ![The chat: the user asks to file a 36 EUR taxi on their Paris trip; only list_trips and ask_expense_policy run, and the assistant answers that the expense-filing tool is not available, while the policy agent says the taxi is within policy](docs/agent365-block.png) |

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

One turn, *"Please file the €220 dinner on my Paris trip"*:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Chat as Chat UI
    participant TA as Travel assistant<br/>(hosted agent)
    participant LL as LiteLLM
    participant A365 as Agent 365
    participant Trips as Trips MCP server
    participant Policy as Expense policy agent<br/>(prompt agent)
    participant Model as Foundry model

    User->>Chat: Message (signed in: chat, gateway and Foundry tokens)
    Chat->>TA: Responses, as the user<br/>+ the user's gateway and Foundry tokens (x-client-*)
    TA->>LL: Model call (the travel assistant's key)
    LL->>Model: LiteLLM's managed identity
    LL-->>TA: Tool call: ask_expense_policy
    TA->>LL: A2A 1.0 SendMessage<br/>(the travel assistant's key + the user's Foundry token)
    LL->>Policy: The user's Foundry token, passed on
    Policy->>LL: Model call (the expense policy agent's key)
    LL->>Model: LiteLLM's managed identity
    Note over Policy: The code interpreter runs policy.py:<br/>4 x 90 = 360 EUR, within the policy
    Policy-->>LL: Answer
    LL-->>TA: Answer
    TA->>LL: Model call, with the policy's answer
    LL-->>TA: Tool call: add_expense
    TA->>LL: MCP tools/call add_expense<br/>(the travel assistant's key + the user's gateway token)
    LL->>A365: Evaluate the call, On-Behalf-Of the user
    A365-->>LL: Allow
    LL->>Trips: The user's gateway token, passed on
    Note over Trips: Checks the token, files the expense<br/>for this user only
    Trips-->>LL: Expense filed
    LL-->>TA: Expense filed
    TA->>LL: Model call, with the result
    LL-->>TA: The answer
    TA-->>Chat: Answer and tool calls, streamed
    Chat-->>User: "Filed the €220 dinner on your Paris trip."
```

| Call | Credential | What the callee sees |
|---|---|---|
| Chat UI → travel assistant | The user's Foundry token, plus the user's gateway and Foundry tokens in `x-client-*` headers, which Foundry passes on to the agent | The signed-in user |
| Travel assistant → LiteLLM → trips MCP server | The agent's LiteLLM key admits the call; LiteLLM passes the user's gateway token on unchanged (`oauth_delegate`) | The user (`oid`), signed in to the chat (`azp`) |
| Travel assistant → LiteLLM → expense policy agent (A2A 1.0) | The agent's LiteLLM key; the user's Foundry token, which LiteLLM passes on | The user (Foundry Agent Consumer role, through the chat users' group) |
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
| [services/chat-ui](services/chat-ui) | The chat (Next.js, CopilotKit, MSAL), in its Foundry mode: it calls the travel assistant as the user, keeps one agent session per chat and shows each tool call as it happens ([services/chat-ui/README.md](services/chat-ui/README.md#foundry-mode)) |
| [src](src) | LiteLLM configuration, the expense policy agent's deployment, a command-line client ([src/README.md](src/README.md)) |
| [infra](infra) | One Terraform root: one file per part of the architecture ([foundry.tf](infra/foundry.tf), [litellm-gateway.tf](infra/litellm-gateway.tf), [trips-mcp.tf](infra/trips-mcp.tf), …), each calling a module of [infra/modules](infra/modules) and wiring it to the others; [connections.tf](infra/connections.tf) connects the chat to the travel assistant; the steps azd runs before and after Terraform are in [infra/hooks](infra/hooks) (one folder per event, run in name order) and [infra/scripts](infra/scripts) |

## Quick start

### 1. Prerequisites

- An Azure subscription.
- In its Microsoft Entra tenant:
  - the right to create app registrations and security groups;
  - a role that can grant tenant-wide admin consent to APIs other than Microsoft Graph, such as Cloud Application Administrator, Application Administrator or AI Administrator. `azd down` needs it again to remove the two consents. The app registrations and the group, which you own, and the Azure resources need no directory role.
- Microsoft Entra ID P1 or P2: only the members of a group can sign in to the chat, and assigning a group to an application needs one of these licences.
- Agent 365 in your tenant, for the governance part.
- Tools:
  - the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli);
  - [azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.37 or later, with the Foundry extensions 1.0 or later;
  - Terraform 1.9 or later;
  - [uv](https://docs.astral.sh/uv/);
  - Node.js 22, only for local checks of the chat UI.

### 2. Deploy

```bash
az login && azd auth login
azd extension install azure.ai.agents azure.ai.projects   # or: azd extension upgrade …
azd env new <name> --location francecentral
azd env set RESOURCE_TAGS "key=value"            # optional: tags your organisation's policies require
azd hooks run preprovision                       # remote Terraform state, model quota check
azd provision --preview                          # read the plan
azd up
```

If the quota check finds too little capacity for the model in your region, pick another deployment type or capacity before `azd up`. For example, `azd env set MODEL_SKU GlobalStandard` (the default, `DataZoneStandard`, keeps data processing in the EU data zone) or `azd env set MODEL_CAPACITY 20`.

`azd up` provisions the infrastructure (one Terraform plan), then deploys the services, in about 25 minutes. Along the way, its hooks ([infra/hooks](infra/hooks)):

- give LiteLLM's identity its database role, configure LiteLLM and deploy the expense policy agent ([src](src)), after provisioning;
- give the travel assistant's identity read access to its own LiteLLM key and the right to publish telemetry, after it is deployed;
- provision once more after the first deployment, so that the container apps switch from their placeholder image's port to their own.

To change an environment later, read the plan before applying it: `azd provision --preview`, then `azd provision`.

### 3. Open and share the chat

Open the chat at `azd env get-value CHAT_UI_URL`.

To share it, add people to the Entra group *Contoso travel assistant users (<environment>)*, of which you are a member and the owner:

```bash
az ad group member add --group "$(azd env get-value CHAT_USERS_GROUP_ID)" --member-id <user object id>
```

Only the group's members can sign in to the chat ([chat-ui.tf](infra/chat-ui.tf)). The group has the Foundry Agent Consumer role on the project, which lets its members call the agents with their own token ([connections.tf](infra/connections.tf)). A new member can use the chat after a few minutes, once the role applies to them.

To try it without the chat:

```bash
uv run python src/ask_travel_assistant.py "What are my upcoming trips?"
```

### 4. Govern with Agent 365

Connect LiteLLM to Agent 365, then block and unblock tools: see [docs/agent365.md](docs/agent365.md).

## Observe

- **Application Insights** receives OpenTelemetry from the chat, the travel assistant and LiteLLM. Each Agent 365 evaluation is a `guardrail` dependency with its verdict, for example `{"verdict": "Allow", "defender_status": "Evaluated"}`.
- **LiteLLM's spend logs** (`/ui`, user `admin`, the admin key in Key Vault as `litellm-master-key`) show each call with the alias of the key that made it.
- **The trips MCP server's log** shows, for each tool call, the user (`oid`) and the application they signed in to (`azp`).

## Design notes

- **Two kinds of agents, two roles.** The travel assistant is code (a hosted agent), so it can bind each request to the user's tokens and build its tools per request. The expense policy agent is configuration (a prompt agent): instructions, a model, the code interpreter. Foundry exposes a prompt agent over A2A directly, so the expense policy agent is the one reached over A2A, with no server code of its own.
- **Figures come from code.** The policy's limits and checks are in [policy.py](agents/expense-policy/skill/scripts/policy.py), which the expense policy agent runs in the code interpreter for every answer. The skill folder follows the open Agent Skills format, so it can also be published as a Foundry skill.
- **One key per agent.** Each agent's LiteLLM key allows exactly the models, MCP servers and A2A agents it uses, and names it in LiteLLM's logs.
- **A user token on every MCP call.** The Agent 365 guardrail evaluates each MCP tool call as the user, and LiteLLM's open-source edition applies guardrails to every key alike. So every MCP call through LiteLLM carries a user token, and the expense policy agent, which acts as itself, calls no MCP server.
- **The user's token reaches the trips server.** LiteLLM passes the user's gateway token on unchanged (`oauth_delegate`), and the trips server checks it (tenant, the gateway app's audience, the `Tools.Use` scope) before any tool runs. Discovery (`initialize`, `tools/list`) needs no token, so that Agent 365 can list the tools with its own key; tool definitions hold no user data. LiteLLM's On-Behalf-Of exchange (`oauth2_token_exchange`) would give the trips server a token of its own audience, but it then needs a user token for discovery as well, which Agent 365 does not send.
- **Credentials.** Users and agents act with Entra tokens: the users' own tokens, managed identities for the services (LiteLLM to the models, the trips MCP server to its storage), and the travel assistant's agent identity (to Key Vault and Application Insights). Each agent's LiteLLM key is kept in Key Vault, and the expense policy agent's in a project connection. The one client secret, the gateway app's (for the Agent 365 guardrail's On-Behalf-Of exchange), is kept in Key Vault and in LiteLLM's database.
- **A responsive chat.** A new hosted-agent session starts a container, which takes a few seconds. The chat starts the agent's session as soon as a chat opens and reuses it for every message of that chat (`agent_session_id`), so answers do not wait for it; tool calls are shown as soon as the agent reports them, since a question to the expense policy agent over A2A takes a few seconds.

## Tech stack

Versions used in November 2026:

| Technology | Role | Version |
|---|---|---|
| [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/) | The project, the model, the hosted agent and the prompt agent | model `gpt-6-luna` |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | The travel assistant (Python) | 1.22 |
| [LiteLLM](https://github.com/BerriAI/litellm) | The gateway for models, MCP and A2A, with the `agent_365` guardrail | v1.106.6 |
| [Microsoft Agent 365](https://learn.microsoft.com/microsoft-agent-365/) | Discovers, blocks and evaluates the MCP tools | |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | The trips MCP server | 2.3 |
| [A2A](https://a2a-protocol.org) | Between the travel assistant and the expense policy agent | 1.0 |
| [CopilotKit](https://www.copilotkit.ai) (AG-UI), [Next.js](https://nextjs.org), [MSAL](https://github.com/AzureAD/microsoft-authentication-library-for-js) | The chat | 1.79, 16.4, 5.25 |
| [OpenTelemetry](https://opentelemetry.io) and [Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview) | Traces and metrics of the chat, the travel assistant and LiteLLM | |
| [Terraform](https://www.terraform.io) and [azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/) | The infrastructure and its deployment | Terraform 1.9+, azd 1.37 with the Foundry extensions 1.0 |
| Azure Container Apps, Azure Database for PostgreSQL, Key Vault, Container Registry, Table storage | LiteLLM, the trips MCP server and the chat, LiteLLM's database, the secrets, the images, the trips | PostgreSQL 18 |

## Documentation

| Document | What it covers |
|---|---|
| [docs/agent365.md](docs/agent365.md) | Connect LiteLLM to Agent 365, then block and unblock a tool |
| [services/chat-ui/README.md](services/chat-ui/README.md) | The chat: settings, sign-in rules, and its Foundry mode |
| [src/README.md](src/README.md) | The scripts that configure LiteLLM, deploy the expense policy agent, and ask the travel assistant from the command line |
| [infra/modules/README.md](infra/modules/README.md) | The Terraform modules, their inputs for a virtual network, and their tests |
| [agents/expense-policy/skill/SKILL.md](agents/expense-policy/skill/SKILL.md) | The expense policy skill, in the open Agent Skills format |
| [AGENTS.md](AGENTS.md) | How to change the sample: rules, checks, conventions |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability, and how to use the sample safely |

## Versions and preview notes

As of November 2026:

- The travel assistant is hosted with `agent-framework-foundry-hosting` 1.0.0b261015, a pre-release package.
- LiteLLM is connected to Agent 365 in the Microsoft 365 admin center (Agents → Settings → Gateways), a setting in preview.
- Agent 365 must be available in your tenant, and so must Microsoft Entra ID P1 or P2: access to the chat is given to a group, and assigning a group (rather than individual users) to an application needs one of these licences ([Prerequisites](#1-prerequisites)).
- The model and its capacity depend on the region: the preprovision hook checks them before anything is deployed.

## Clean up

Delete the two agents first, so that their Entra agent identities go with them:

```bash
for agent in travel-assistant expense-policy; do
  az rest --method delete --resource https://ai.azure.com \
    --url "$(azd env get-value FOUNDRY_PROJECT_ENDPOINT)/agents/$agent?api-version=v1&force=true"
done
azd down --purge
```

`azd down --purge` deletes the resource group and purges the Key Vault and the Foundry account. The two app registrations (the gateway's and the chat's) and the chat users' group are deleted with the rest. Remove the LiteLLM gateway from Agent 365 (Gateways) too.

## Cost

Running the sample costs about **$2.50 a day, or $75 a month**, and most of it is billed whether or not anyone uses it. The figures below are list prices in France Central, in US dollars, from the [Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices) on 2026-11-09. A deployment left idle for a full day was billed $2.53 for its resources.

| Resource | Per day | Per month | What drives it |
|---|---:|---:|---|
| Azure Container Apps: LiteLLM (with its telemetry collector), the trips MCP server and the chat, one replica each, 2 vCPU and 4 GiB in total | $1.56 | $47.30 | Always on, at the idle rate between requests |
| Azure Database for PostgreSQL: Burstable B1ms, 32 GiB of storage | $0.60 | $18.13 | Always on |
| Azure Container Registry: Basic | $0.17 | $5.07 | Always on |
| Log Analytics: about 0.07 GB of logs and traces a day | $0 to $0.19 | $0 to $5.88 | The first 5 GB a month of a billing account are included, then $2.76 per GB |
| Foundry: the travel assistant's sessions (0.5 vCPU, 1 GiB) | | | $0.07 per hour a session runs |
| Foundry: the model, `gpt-6-luna` (Data Zone Standard) | | | $0.12 per million input tokens, $0.60 per million output tokens |
| Key Vault, Table storage, the Terraform state | under $0.01 | under $0.30 | Per operation and per GB stored |

Using the sample adds little to that:
- **An hour of conversations** costs about $0.25 at most: the travel assistant's session, the container apps at their active rate, and the model's tokens.
- **A full day of testing** used $0.03 of model tokens.
- **Image builds** in the registry, when deploying, cost $0.25 on the day of the first deployment.

These costs are not included:
- Microsoft 365 and Agent 365 licences, and Microsoft Entra ID P1 or P2.
- Microsoft Defender for Cloud plans enabled on the subscription, which are billed per resource ($0.43 a day on the subscription used for the measurement).

To stop all charges, delete the environment ([Clean up](#clean-up)).

## License

[MIT](LICENSE)
