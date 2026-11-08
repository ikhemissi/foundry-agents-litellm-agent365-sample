#!/usr/bin/env bash
# azd postprovision hook: what Terraform cannot do, in order. Every step is idempotent.
#   1. LiteLLM's identity gets its PostgreSQL role (as the server's Entra administrator: the deploying user).
#   2. LiteLLM is configured through its admin API: the trips MCP server, the expense policy agent (A2A), one key per
#      agent, the Agent 365 guardrail.
#   3. The expense policy agent is deployed through the Foundry REST API (it uses its LiteLLM key from step 2).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

infra/scripts/litellm-database-role.sh
uv run python src/configure_gateway.py
uv run python src/deploy_policy_agent.py
