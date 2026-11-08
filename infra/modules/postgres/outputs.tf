# id and host wait for the server-level operations above, so that a database a workload creates on the server does not
# run concurrently with them ("ServerIsBusy").
output "id" {
  value      = azurerm_postgresql_flexible_server.main.id
  depends_on = [azurerm_private_endpoint.main]
}

output "name" {
  value = azurerm_postgresql_flexible_server.main.name
}

output "host" {
  value      = azurerm_postgresql_flexible_server.main.fqdn
  depends_on = [azurerm_private_endpoint.main]
}
