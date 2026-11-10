#!/usr/bin/env bash
# Deploys the expense policy prompt agent through the Foundry REST API, with its LiteLLM key from the previous step
# (src/deploy_policy_agent.py). Idempotent.
set -euo pipefail
uv run python src/deploy_policy_agent.py
