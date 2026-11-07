# Outputs become azd environment values. No secrets: the gateway's client secret stays in Key Vault.

output "GATEWAY_CLIENT_ID" { value = azuread_application.gateway.client_id }
output "GATEWAY_SCOPE" { value = "${azuread_application_identifier_uri.gateway.identifier_uri}/${local.gateway_scope}" }
output "GATEWAY_SECRET_NAME" { value = azurerm_key_vault_secret.gateway_client_secret.name }
output "TRIPS_API_AUDIENCE" { value = azuread_application_identifier_uri.trips.identifier_uri }
# What LiteLLM asks Entra for in the On-Behalf-Of exchange for the trips MCP server.
output "TRIPS_API_SCOPE" { value = "${azuread_application_identifier_uri.trips.identifier_uri}/.default" }
# The chat UI asks for a gateway token for its users (its gateway_scope input).
output "CHAT_UI_GATEWAY_SCOPE" { value = "${azuread_application_identifier_uri.gateway.identifier_uri}/${local.gateway_scope}" }
