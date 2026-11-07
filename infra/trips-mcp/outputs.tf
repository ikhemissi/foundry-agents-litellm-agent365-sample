# Outputs become azd environment values. The URL resolves only inside the Container Apps environment (LiteLLM).

output "TRIPS_MCP_APP_NAME" { value = azurerm_container_app.trips.name }
output "TRIPS_MCP_URL" { value = "https://${azurerm_container_app.trips.ingress[0].fqdn}/mcp" }
output "TRIPS_MCP_STORAGE_NAME" { value = azurerm_storage_account.trips.name }
