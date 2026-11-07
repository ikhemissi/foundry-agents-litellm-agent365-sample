#!/usr/bin/env bash
# azd postprovision hook of the chat-ui layer: the gateway app (entra-apps layer) must pre-authorize the chat UI's app
# registration, which exists only once the chat-ui layer is provisioned; so the first time, the entra-apps layer is
# provisioned again, now with CHAT_UI_CLIENT_ID. Later runs find it pre-authorized: nothing to do.
set -euo pipefail
: "${AZURE_ENV_NAME:?}" "${GATEWAY_CLIENT_ID:?}" "${CHAT_UI_CLIENT_ID:?}"

preauthorized="$(az ad app show --id "$GATEWAY_CLIENT_ID" --query "api.preAuthorizedApplications[].appId" -o tsv)"
if ! grep -qx "$CHAT_UI_CLIENT_ID" <<<"$preauthorized"; then
  echo "Pre-authorizing the chat UI on the gateway app: provisioning the entra-apps layer again"
  azd provision entra-apps -e "$AZURE_ENV_NAME" --no-prompt
fi
