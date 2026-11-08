# No secrets: the admin key stays in Key Vault (master_key_secret_name).

output "url" {
  value = "https://${azurerm_container_app.gateway.ingress[0].fqdn}"
}

output "app_name" {
  value = azurerm_container_app.gateway.name
}

output "identity_name" {
  value = azurerm_user_assigned_identity.gateway.name
}

output "identity_principal_id" {
  value = azurerm_user_assigned_identity.gateway.principal_id
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.gateway.name
}

output "master_key_secret_name" {
  value = azurerm_key_vault_secret.master_key.name
}
