# Both wait for the secrets officers' roles, so that secrets written with them (azurerm_key_vault_secret) succeed.
output "id" {
  value      = azurerm_key_vault.main.id
  depends_on = [azurerm_role_assignment.secrets_officers]
}

output "name" {
  value = azurerm_key_vault.main.name
}

output "uri" {
  value      = azurerm_key_vault.main.vault_uri
  depends_on = [azurerm_role_assignment.secrets_officers]
}
