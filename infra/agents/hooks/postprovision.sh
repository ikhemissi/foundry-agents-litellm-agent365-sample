#!/usr/bin/env bash
# azd postprovision hook of the agents layer: configures LiteLLM, then deploys the expense policy agent (which uses
# the LiteLLM key the first script creates). Both scripts are idempotent.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
uv run python src/configure_gateway.py
uv run python src/deploy_policy_agent.py
