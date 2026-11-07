# The chat UI (services/chat-ui): a public container app where signed-in users chat with the model through a gateway
# and see each MCP tool call. Users sign in with Entra (MSAL in the browser); the app validates their tokens for its
# own API scope and lets in only the listed users (the deployer). The gateway is whichever the project provisions:
# - LiteLLM (LITELLM_URL): the app calls it with a team's virtual key, and LiteLLM runs the MCP tools;
# - API Management (APIM_MODELS_URL): the app calls it with the user's own token, and runs the MCP tools itself
#   through it (CHAT_UI_MCP_SERVERS);
# - a Foundry hosted agent (CHAT_UI_FOUNDRY_AGENT): the app calls the agent with the user's Foundry token and forwards
#   the user's gateway token; the agent runs its tools as the user. Admin consent for Foundry's API is granted here.

data "azurerm_client_config" "current" {}

locals {
  token = substr(sha1("${var.subscription_id}-${var.environment_name}"), 0, 8)

  extra_tag_pairs = [for pair in split(",", var.tags) : split("=", pair) if trimspace(pair) != ""]
  extra_tags = {
    for pair in local.extra_tag_pairs : trimspace(pair[0]) => trimspace(join("=", slice(pair, 1, length(pair))))
  }
  tags = merge(local.extra_tags, { "azd-env-name" = var.environment_name })

  app_name = "ca-chat-${local.token}"
  title    = coalesce(var.title, "Chat")
  # Which gateway the UI talks to follows from which gateway layer the project has; with both, API Management (a
  # project can show a second gateway next to the one its app uses). A Foundry agent, when named, comes first.
  gateway       = var.foundry_agent != "" ? "foundry" : var.apim_models_url != "" ? "apim" : "litellm"
  uses_team_key = local.gateway == "litellm"
  # With LiteLLM, the Key Vault secret with the team's key: it must exist before this layer is provisioned (README).
  litellm_key_secret_name = local.uses_team_key ? coalesce(var.litellm_key_secret_name, "litellm-key-chat-ui") : ""
  # Known before the app exists, so that the sign-in redirect and the app's own settings need no second pass.
  origin = "https://${local.app_name}.${var.container_apps_default_domain}"
  scope  = "Chat.Use"
}

resource "random_uuid" "chat_scope" {}

# One app registration: the single-page application users sign in to, and the API scope its server checks.
resource "azuread_application" "ui" {
  display_name     = "${local.title} (${var.environment_name})"
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azurerm_client_config.current.object_id]

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = random_uuid.chat_scope.result
      value                      = local.scope
      type                       = "User"
      enabled                    = true
      admin_consent_display_name = "Use the chat"
      admin_consent_description  = "Allows the chat to call its server on behalf of the signed-in user."
      user_consent_display_name  = "Use the chat"
      user_consent_description   = "Allows the chat to call its server on your behalf."
    }
  }

  lifecycle {
    # The identifier URI and the redirect URIs are managed by their own resources below.
    ignore_changes = [identifier_uris, single_page_application]
  }
}

# api://<appId>: accepted by the tenant's default app management policy (custom URIs may be rejected).
resource "azuread_application_identifier_uri" "ui" {
  application_id = azuread_application.ui.id
  identifier_uri = "api://${azuread_application.ui.client_id}"
}

resource "azuread_application_redirect_uris" "ui" {
  application_id = azuread_application.ui.id
  type           = "SPA"
  redirect_uris  = ["${local.origin}/auth/callback", "http://localhost:3000/auth/callback"]
}

resource "azuread_service_principal" "ui" {
  client_id = azuread_application.ui.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}

resource "azurerm_user_assigned_identity" "ui" {
  name                = "id-chat-${local.token}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = local.tags
}

# With LiteLLM, read access to the team's key only, not to the vault (which also holds the gateway's admin key).
# Application Insights has local authentication disabled: the app sends its telemetry with this role.
resource "azurerm_role_assignment" "ui_telemetry" {
  scope                = var.application_insights_id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_user_assigned_identity.ui.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "ui_team_key" {
  count                = local.uses_team_key ? 1 : 0
  scope                = "${var.key_vault_id}/secrets/${local.litellm_key_secret_name}"
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ui.principal_id
  principal_type       = "ServicePrincipal"
}

# Foundry mode: the browser asks for the user's token for Foundry's API (https://ai.azure.com/user_impersonation, the
# "Azure Machine Learning Services" application). Tenant-wide admin consent, so that users see no consent prompt.
data "azuread_service_principal" "foundry_api" {
  count     = local.gateway == "foundry" ? 1 : 0
  client_id = "18a66f5f-dbdf-4c17-9dd7-1634712a9cbe"
}

resource "azuread_service_principal_delegated_permission_grant" "foundry_api" {
  count                                = local.gateway == "foundry" ? 1 : 0
  service_principal_object_id          = azuread_service_principal.ui.object_id
  resource_service_principal_object_id = data.azuread_service_principal.foundry_api[0].object_id
  claim_values                         = ["user_impersonation"]
}
