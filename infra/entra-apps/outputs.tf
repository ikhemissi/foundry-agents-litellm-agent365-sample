# Outputs become azd environment values. No secrets: the gateway's client secret stays in Key Vault.

output "GATEWAY_CLIENT_ID" { value = azuread_application.gateway.client_id }
output "GATEWAY_SCOPE" { value = "${azuread_application_identifier_uri.gateway.identifier_uri}/${local.gateway_scope}" }
output "GATEWAY_SECRET_NAME" { value = azurerm_key_vault_secret.gateway_client_secret.name }
# The audience of the user tokens the trips MCP server accepts (LiteLLM passes them on).
output "GATEWAY_AUDIENCE" { value = azuread_application_identifier_uri.gateway.identifier_uri }
# The chat UI asks for a gateway token for its users (its gateway_scope input).
output "CHAT_UI_GATEWAY_SCOPE" { value = "${azuread_application_identifier_uri.gateway.identifier_uri}/${local.gateway_scope}" }
