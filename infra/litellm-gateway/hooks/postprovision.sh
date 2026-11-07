#!/usr/bin/env bash
# azd postprovision hook of the litellm-gateway layer: gives the gateway's managed identity its PostgreSQL role and
# rights on its database (as the server's Entra administrator), then restarts the gateway if it is not ready yet, so
# that it applies its migrations with the new role. Idempotent.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${AZURE_RESOURCE_GROUP:?}" "${LITELLM_APP_NAME:?}" "${LITELLM_URL:?}" "${LITELLM_IDENTITY_NAME:?}" \
  "${LITELLM_IDENTITY_PRINCIPAL_ID:?}" "${LITELLM_DATABASE_NAME:?}"

"$HERE/../../postgres/scripts/grant-identity.sh" "$LITELLM_IDENTITY_NAME" "$LITELLM_IDENTITY_PRINCIPAL_ID" \
  "$LITELLM_DATABASE_NAME"

if curl -fsS -o /dev/null --max-time 10 "$LITELLM_URL/health/readiness"; then
  echo "LiteLLM is ready: $LITELLM_URL"
  exit 0
fi
revision="$(az containerapp show -n "$LITELLM_APP_NAME" -g "$AZURE_RESOURCE_GROUP" --query properties.latestRevisionName -o tsv)"
echo "LiteLLM is not ready yet: restarting $revision so that it connects with its database role"
az containerapp revision restart -n "$LITELLM_APP_NAME" -g "$AZURE_RESOURCE_GROUP" --revision "$revision" -o none
