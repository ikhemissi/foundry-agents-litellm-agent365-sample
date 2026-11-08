# The chat UI (services/chat-ui, deployed by azd): a public container app where signed-in users chat with the travel
# assistant. Users sign in with Entra (MSAL in the browser); the app checks their tokens for its own API scope and lets
# in only the listed users (the deployer). It calls the agent with the user's Foundry token and forwards the user's
# gateway token, so that the agent acts as the user.

variable "chat_ui_image" {
  description = "The image azd deployed (SERVICE_CHAT_UI_IMAGE_NAME). Empty before the first deployment."
  type        = string
}

locals {
  chat_ui_name = "ca-chat-${local.token}"
  # Known before the app exists, so that the sign-in redirect and the app's own settings need no second pass.
  chat_ui_origin = "https://${local.chat_ui_name}.${module.container_apps_environment.default_domain}"
  chat_ui_scope  = "Chat.Use"
  # Foundry's API (https://ai.azure.com), the "Azure Machine Learning Services" application.
  foundry_api_app_id = "18a66f5f-dbdf-4c17-9dd7-1634712a9cbe"
}

resource "random_uuid" "chat_ui_scope" {}

# One app registration: the single-page application users sign in to, and the API scope its server checks.
resource "azuread_application" "chat_ui" {
  display_name     = "Contoso travel assistant (${var.environment_name})"
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azurerm_client_config.current.object_id]

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = random_uuid.chat_ui_scope.result
      value                      = local.chat_ui_scope
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
resource "azuread_application_identifier_uri" "chat_ui" {
  application_id = azuread_application.chat_ui.id
  identifier_uri = "api://${azuread_application.chat_ui.client_id}"
}

resource "azuread_application_redirect_uris" "chat_ui" {
  application_id = azuread_application.chat_ui.id
  type           = "SPA"
  redirect_uris  = ["${local.chat_ui_origin}/auth/callback", "http://localhost:3000/auth/callback"]
}

resource "azuread_service_principal" "chat_ui" {
  client_id = azuread_application.chat_ui.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}

# Tenant-wide admin consent for the user's Foundry token, so that users see no consent prompt.
data "azuread_service_principal" "foundry_api" {
  client_id = local.foundry_api_app_id
}

resource "azuread_service_principal_delegated_permission_grant" "chat_ui_foundry" {
  service_principal_object_id          = azuread_service_principal.chat_ui.object_id
  resource_service_principal_object_id = data.azuread_service_principal.foundry_api.object_id
  claim_values                         = ["user_impersonation"]
}

module "chat_ui" {
  source                                 = "./modules/container-app"
  name                                   = local.chat_ui_name
  azd_service_name                       = "chat-ui"
  image                                  = var.chat_ui_image
  port                                   = 3000
  health_path                            = "/api/health"
  external                               = true
  cpu                                    = 0.5
  memory                                 = "1Gi"
  resource_group_name                    = azurerm_resource_group.main.name
  location                               = var.location
  tags                                   = local.tags
  container_apps_environment_id          = module.container_apps_environment.id
  registry_server                        = module.container_registry.login_server
  registry_pull_identity_id              = module.container_registry.pull_identity_id
  application_insights_connection_string = module.monitoring.application_insights_connection_string

  env = {
    CHAT_GATEWAY            = "foundry"
    GATEWAY_URL             = module.foundry.project_endpoint
    FOUNDRY_AGENT           = "travel-assistant"
    GATEWAY_SCOPE           = "${azuread_application_identifier_uri.gateway.identifier_uri}/${local.gateway_scope}"
    CHAT_MODEL              = module.foundry.model_deployment_name
    CHAT_TITLE              = "Contoso travel assistant"
    CHAT_INTRO              = "A Foundry hosted agent that acts for you: it reads your trips and files expenses through LiteLLM (MCP, governed by Agent 365), and asks Contoso's expense policy agent over A2A 1.0. Each tool call is shown under the answer."
    UI_TENANT_ID            = data.azurerm_client_config.current.tenant_id
    UI_CLIENT_ID            = azuread_application.chat_ui.client_id
    UI_SCOPE                = local.chat_ui_scope
    UI_ORIGIN               = local.chat_ui_origin
    ALLOWED_USER_OBJECT_IDS = data.azurerm_client_config.current.object_id
  }

  role_assignments = {
    telemetry = { scope = module.monitoring.application_insights_id, role = "Monitoring Metrics Publisher" }
  }
}

output "CHAT_UI_URL" { value = module.chat_ui.url }
