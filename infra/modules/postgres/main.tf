# A PostgreSQL Flexible Server with Entra authentication only (no passwords). Workloads create their own database on it
# and get a role from the Entra administrator (scripts/postgres-grant-identity.sh). Given a private endpoint subnet,
# it also gets a private endpoint.

data "azurerm_client_config" "current" {}

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = var.name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = "18"
  sku_name                      = var.sku_name
  storage_mb                    = 32768
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false
    tenant_id                     = data.azurerm_client_config.current.tenant_id
  }

  lifecycle {
    # Azure picks the availability zone; changing it is not a configuration drift.
    ignore_changes = [zone]
  }
}

# PostgreSQL rejects concurrent server-level operations ("ServerIsBusy"): the resources below are chained with
# depends_on so they are applied one at a time.

# Lets Azure services without a fixed outbound IP (Container Apps outside a virtual network) reach the server; access
# still requires an Entra token.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  count            = var.public_network_access_enabled && var.allow_azure_services ? 1 : 0
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "client" {
  count            = var.public_network_access_enabled && var.client_ip_address != null ? 1 : 0
  name             = "allow-client"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = var.client_ip_address
  end_ip_address   = var.client_ip_address
  depends_on       = [azurerm_postgresql_flexible_server_firewall_rule.azure_services]
}

resource "azurerm_postgresql_flexible_server_active_directory_administrator" "main" {
  count               = var.administrator == null ? 0 : 1
  server_name         = azurerm_postgresql_flexible_server.main.name
  resource_group_name = var.resource_group_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  object_id           = var.administrator.object_id
  principal_name      = var.administrator.principal_name
  principal_type      = var.administrator.principal_type
  depends_on          = [azurerm_postgresql_flexible_server_firewall_rule.client]
}

resource "azurerm_private_endpoint" "main" {
  count               = var.private_endpoint_subnet_id == null ? 0 : 1
  name                = "pe-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = var.name
    private_connection_resource_id = azurerm_postgresql_flexible_server.main.id
    subresource_names              = ["postgresqlServer"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.private_dns_zone_ids["privatelink.postgres.database.azure.com"]]
  }

  depends_on = [azurerm_postgresql_flexible_server_active_directory_administrator.main]
}
