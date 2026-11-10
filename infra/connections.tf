# How the optional parts of this project connect: the project's own file (not from a block), generated with the
# project's choices. Change it when the parts change; block files reference only the parts their block requires.

# The chat UI talks to the travel assistant (a Foundry hosted agent) as the signed-in user: with the user's Foundry
# token for the agent's endpoint, and the user's token for the gateway app, which the agent forwards to LiteLLM.
locals {
  chat_ui_gateway = {
    env = {
      CHAT_GATEWAY  = "foundry"
      GATEWAY_URL   = module.foundry.project_endpoint
      FOUNDRY_AGENT = "travel-assistant"
      GATEWAY_SCOPE = "${azuread_application_identifier_uri.gateway.identifier_uri}/${local.gateway_scope}"
    }
    key_vault_secrets = {}
    role_assignments  = {}
  }
  # Foundry's API (https://ai.azure.com), the "Azure Machine Learning Services" application.
  foundry_api_app_id = "18a66f5f-dbdf-4c17-9dd7-1634712a9cbe"
}

# The gateway app lets the chat ask for a gateway token without a consent prompt (after the Azure CLI: one at a time).
resource "azuread_application_pre_authorized" "chat_ui" {
  application_id       = azuread_application.gateway.id
  authorized_client_id = azuread_application.chat_ui.client_id
  permission_ids       = [random_uuid.gateway_scope.result]

  depends_on = [azuread_application_pre_authorized.azure_cli]
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

# The chat's users, the deployer included, may call the agents' endpoints (Responses and A2A) with their own token.
resource "azurerm_role_assignment" "chat_users_agent_consumer" {
  scope                = module.foundry.project_id
  role_definition_name = "Foundry Agent Consumer"
  principal_id         = azuread_group.chat_users.object_id
  principal_type       = "Group"
}
