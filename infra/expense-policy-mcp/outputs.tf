# Outputs become azd environment values. The URL resolves only inside the Container Apps environment (LiteLLM).

output "EXPENSE_POLICY_MCP_APP_NAME" { value = azurerm_container_app.policy.name }
output "EXPENSE_POLICY_MCP_URL" { value = "https://${azurerm_container_app.policy.ingress[0].fqdn}/mcp" }
