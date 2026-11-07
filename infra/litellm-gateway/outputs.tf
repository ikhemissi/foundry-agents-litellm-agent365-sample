# Outputs become azd environment values (prefixed LITELLM_). No secrets: the admin key stays in Key Vault
# (az keyvault secret show --vault-name "$PLATFORM_KEY_VAULT_NAME" -n "$LITELLM_MASTER_KEY_SECRET_NAME").

output "LITELLM_URL" { value = "https://${azurerm_container_app.gateway.ingress[0].fqdn}" }
output "LITELLM_APP_NAME" { value = azurerm_container_app.gateway.name }
output "LITELLM_IDENTITY_NAME" { value = azurerm_user_assigned_identity.gateway.name }
output "LITELLM_IDENTITY_PRINCIPAL_ID" { value = azurerm_user_assigned_identity.gateway.principal_id }
output "LITELLM_DATABASE_NAME" { value = azurerm_postgresql_flexible_server_database.gateway.name }
output "LITELLM_MASTER_KEY_SECRET_NAME" { value = azurerm_key_vault_secret.master_key.name }
