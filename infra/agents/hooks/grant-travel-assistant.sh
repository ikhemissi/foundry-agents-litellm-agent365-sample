#!/usr/bin/env bash
# azd postdeploy hook of the travel-assistant service: the hosted agent's identity exists only once the agent is
# deployed, so its roles are given here: read its own LiteLLM key (that secret only) and publish telemetry to
# Application Insights (which accepts only Entra-authenticated telemetry). Idempotent.
set -euo pipefail
: "${FOUNDRY_PROJECT_ENDPOINT:?}" "${PLATFORM_KEY_VAULT_ID:?}" "${PLATFORM_APPLICATION_INSIGHTS_ID:?}"

principal="$(az rest --method get --resource https://ai.azure.com \
  --url "$FOUNDRY_PROJECT_ENDPOINT/agents/travel-assistant?api-version=v1" \
  --query versions.latest.instance_identity.principal_id --output tsv)"
grant() {
  az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
    --role "$1" --scope "$2" --output none
}
grant "Key Vault Secrets User" "$PLATFORM_KEY_VAULT_ID/secrets/litellm-key-travel-assistant"
grant "Monitoring Metrics Publisher" "$PLATFORM_APPLICATION_INSIGHTS_ID"
echo "travel-assistant ($principal): Key Vault secret and telemetry roles granted"
