#!/usr/bin/env bash
# Run by the postprovision hook: gives the LiteLLM gateway's managed identity its PostgreSQL role and
# rights on its database (as the server's Entra administrator), then restarts the gateway if it is not ready yet, so
# that it applies its migrations with the new role, and waits until it is ready (the next step configures it).
# Idempotent.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${AZURE_RESOURCE_GROUP:?}" "${LITELLM_APP_NAME:?}" "${LITELLM_URL:?}" "${LITELLM_IDENTITY_NAME:?}" \
  "${LITELLM_IDENTITY_PRINCIPAL_ID:?}" "${LITELLM_DATABASE_NAME:?}"

"$HERE/postgres-grant-identity.sh" "$LITELLM_IDENTITY_NAME" "$LITELLM_IDENTITY_PRINCIPAL_ID" \
  "$LITELLM_DATABASE_NAME"

if curl -fsS -o /dev/null --max-time 10 "$LITELLM_URL/health/readiness"; then
  echo "LiteLLM is ready: $LITELLM_URL"
  exit 0
fi
revision="$(az containerapp show -n "$LITELLM_APP_NAME" -g "$AZURE_RESOURCE_GROUP" --query properties.latestRevisionName -o tsv)"
echo "LiteLLM is not ready yet: restarting $revision so that it connects with its database role"
az containerapp revision restart -n "$LITELLM_APP_NAME" -g "$AZURE_RESOURCE_GROUP" --revision "$revision" -o none

# The first start applies LiteLLM's database migrations: up to 5 minutes (its startup probe allows as much).
for _ in $(seq 60); do
  if curl -fsS -o /dev/null --max-time 10 "$LITELLM_URL/health/readiness"; then
    echo "LiteLLM is ready: $LITELLM_URL"
    exit 0
  fi
  sleep 10
done
echo "LiteLLM is still not ready after 10 minutes: see its logs (az containerapp logs show -n $LITELLM_APP_NAME -g $AZURE_RESOURCE_GROUP)" >&2
exit 1
