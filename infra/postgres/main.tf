# PostgreSQL layer: one Flexible Server with Entra authentication only (no passwords). Each workload layer creates its
# own database on it (POSTGRES_SERVER_ID) and, in its postprovision hook, gives its managed identity a role with
# scripts/grant-identity.sh, run as the server's Entra administrator (the deploying user in dev).

data "azurerm_client_config" "current" {}

data "azuread_user" "deployer" {
  count     = var.deployer_is_user ? 1 : 0
  object_id = data.azurerm_client_config.current.object_id
}

data "http" "deployer_ip" {
  count = var.allow_deployer_ip ? 1 : 0
  url   = "https://api.ipify.org"
}

locals {
  token = substr(sha1("${var.subscription_id}-${var.environment_name}"), 0, 8)

  extra_tag_pairs = [for pair in split(",", var.tags) : split("=", pair) if trimspace(pair) != ""]
  extra_tags = {
    for pair in local.extra_tag_pairs : trimspace(pair[0]) => trimspace(join("=", slice(pair, 1, length(pair))))
  }
  tags = merge(local.extra_tags, { "azd-env-name" = var.environment_name })

  sku_name = coalesce(var.postgres_sku, "B_Standard_B1ms")
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "psql-${var.environment_name}-${local.token}"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = "18"
  sku_name                      = local.sku_name
  storage_mb                    = 32768
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  public_network_access_enabled = true
  tags                          = local.tags

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

# Lets Container Apps (no fixed outbound IP without a VNet) reach the server; access still requires an Entra token.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "developer" {
  count            = var.allow_deployer_ip ? 1 : 0
  name             = "allow-deployer"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = chomp(data.http.deployer_ip[0].response_body)
  end_ip_address   = chomp(data.http.deployer_ip[0].response_body)
  depends_on       = [azurerm_postgresql_flexible_server_firewall_rule.azure_services]
}

resource "azurerm_postgresql_flexible_server_active_directory_administrator" "developer" {
  count               = var.deployer_is_user ? 1 : 0
  server_name         = azurerm_postgresql_flexible_server.main.name
  resource_group_name = var.resource_group_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  object_id           = data.azurerm_client_config.current.object_id
  principal_name      = data.azuread_user.deployer[0].user_principal_name
  principal_type      = "User"
  depends_on          = [azurerm_postgresql_flexible_server_firewall_rule.developer]
}
