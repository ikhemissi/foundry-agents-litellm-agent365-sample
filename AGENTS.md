# AGENTS.md — Foundry agents with LiteLLM, governed by Agent 365

This repository is a **sample**: a working, documented example of Microsoft Foundry agents using models, MCP servers and an A2A 1.0 agent through a LiteLLM gateway, governed by Microsoft Agent 365. People read it to learn and reuse the pattern: it must be correct, readable and kept positive and factual. Read [README.md](README.md) first.

## What it shows

- **Travel assistant** (`agents/travel-assistant`): a Foundry **hosted** agent (Agent Framework). It acts **as the signed-in user** towards the trips MCP server (through LiteLLM) and the expense policy agent (A2A 1.0 through LiteLLM), and uses its own LiteLLM key for the model.
- **Expense policy agent** (`agents/expense-policy`): a Foundry **prompt** agent, the A2A 1.0 target. Its policy is a skill in the open Agent Skills format (`skill/SKILL.md` as instructions, `skill/scripts/policy.py` run by the code interpreter, so every figure is computed by code). It uses its own LiteLLM key for its model and calls no MCP server. Deployed by `src/deploy_policy_agent.py`.
- **Trips MCP server** (`services/trips-mcp`): Contoso's fictional trips, per user.
- **LiteLLM** (`infra/litellm-gateway`, configured by `src/configure_gateway.py`): one key per agent, the trips MCP server (the user's token passed on: `oauth_delegate`), the A2A agent, the Agent 365 guardrail on every MCP call (so every MCP call needs a user token).
- **Agent 365** governs the MCP servers LiteLLM exposes (discovery, block and unblock, per tool) and evaluates each tool call as the user (guardrail).

## Rules

- **Never commit secrets**, keys, tokens, tenant or subscription IDs, or real user data. Use your own Entra identity (Azure CLI) and managed identities; local settings go to `.env` (git-ignored). The only client secret (the gateway app's, for LiteLLM's On-Behalf-Of exchanges) lives in Key Vault.
- **Public content:** factual, dated observations and neutral guidance; no customer, employer-internal or personal details. Every figure an agent states comes from code: the policy's amounts and computations live only in `agents/expense-policy/skill/scripts/policy.py`.
- **Identity on every hop is part of the sample:** a change that alters which identity reaches a service updates the identity table in the README.
- **Ask before deciding** anything that changes the design, the scope or the behaviour; propose a default.
- **Commits:** conventional commits (`feat(agents): …`, `fix(infra): …`, `docs: …`), ending with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- **Spec-driven:** larger changes start as an OpenSpec change (`/opsx-propose`), see `openspec/`.

## Infrastructure

- **Layers:** `azure.yaml` lists the azd layers (`infra/<layer>/`, one Terraform root and state each) in provisioning order. `infra/azure-platform`, `infra/foundry-model`, `infra/postgres`, `infra/litellm-gateway` and `infra/chat-ui` come from shared building blocks: keep them as they are, so that their improvements can be merged in later. The sample's own layers: `infra/entra-apps`, `infra/trips-mcp`, `infra/agents`.
- **Gateway settings** (MCP servers, A2A agents, keys, guardrails) go through LiteLLM's admin API (`src/configure_gateway.py`), not into its configuration file.
- **Checks:** in `services/trips-mcp`: `uvx ruff check . && uv run --no-project --with-requirements requirements.txt --with-requirements requirements-dev.txt pytest`; in `agents/travel-assistant`: the same with `--python 3.13`; in `agents/expense-policy`: `uvx ruff check . && uv run --no-project --with-requirements requirements-dev.txt pytest`; in `src`: `uvx ruff check .`; in `services/chat-ui`: `npm ci && npm run typecheck && npm run lint && npm test && npm run build`; for a layer: `terraform -chdir=infra/<layer> init -backend=false && terraform -chdir=infra/<layer> validate`.
- **Before every `azd provision`:** `azd hooks run preprovision`, then `azd provision <layer> --preview` for each layer you change (azd previews one layer at a time), and read the plan.

## Code humans can maintain

Everything here must be maintainable by human developers, whoever (or whatever) wrote it. A developer new to the project understands a module in minutes and changes it with confidence.

- **Simple and explicit over clever:** no metaprogramming, hidden magic or generic frameworks; an abstraction only when a second real use exists.
- **One role per unit:** a module states its role in one or two lines at the top; a function does one thing and fits on a screen (about 40 lines), otherwise split it into named steps.
- **Names carry meaning:** domain words, full words, booleans that read as questions; no single letters except short loop indices.
- **Flat control flow:** early returns, named intermediate values, no dense one-liners or formatter opt-outs.
- **Comments explain why** (the decision, the constraint, a link to the design or ADR), never what the code already says.
- **Consistency beats preference:** follow the patterns already in the repository before introducing a new one.
- **Few dependencies:** ask before adding one; prefer the standard library and what is already used.
- **Tests read as documentation:** named after the behaviour or spec scenario they check; arrange, act, assert.
- **Read your diff as a reviewer before calling a change done;** if a piece cannot be explained simply, rewrite it.

## Known pitfalls

If `.fast-start/pitfalls.md` exists (local only, git-ignored: never commit, copy or quote it), read it before changing
infrastructure or services: it lists pitfalls known for this kind of project.

- None recorded yet.
Add a pitfall here every time something bites you, in one line: the symptom, then what to do.
