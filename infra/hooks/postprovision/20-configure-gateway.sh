#!/usr/bin/env bash
# Configures LiteLLM through its admin API: the trips MCP server, the expense policy agent (A2A), one key per agent,
# the Agent 365 guardrail (src/configure_gateway.py). Idempotent.
set -euo pipefail
uv run python src/configure_gateway.py
