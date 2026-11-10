#!/usr/bin/env bash
# Gives LiteLLM's identity its PostgreSQL role, then waits until the gateway is ready (later steps configure it).
set -euo pipefail
infra/scripts/litellm-database-role.sh
