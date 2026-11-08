#!/usr/bin/env bash
# azd preprovision hook: makes sure the Terraform state backend exists and is configured for this environment, then
# fails fast if the model cannot be deployed in the region. `azd provision --preview` does not run hooks: run
# `azd hooks run preprovision` once before the first preview.
set -euo pipefail
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"

if [[ -n "${RS_STORAGE_ACCOUNT:-}" && -n "${RS_RESOURCE_GROUP:-}" && -n "${RS_CONTAINER_NAME:-}" ]]; then
  echo "Terraform state backend: $RS_STORAGE_ACCOUNT/$RS_CONTAINER_NAME"
else
  "$SCRIPTS/bootstrap-tfstate.sh" "${AZURE_LOCATION:-francecentral}"
fi
"$SCRIPTS/check-model-quota.sh"
