# Outputs become azd environment values (prefixed POSTGRES_), read by the workload layers and the scripts. No secrets.

output "POSTGRES_SERVER_ID" { value = azurerm_postgresql_flexible_server.main.id }
output "POSTGRES_SERVER_NAME" { value = azurerm_postgresql_flexible_server.main.name }
output "POSTGRES_HOST" { value = azurerm_postgresql_flexible_server.main.fqdn }
