# PostgreSQL for LiteLLM's state (keys, MCP servers, guardrails, spend logs), with Entra authentication only. In
# development, the deploying user is the server's Entra administrator: the postprovision hook gives LiteLLM's identity
# its role (scripts/postgres-grant-identity.sh), and scripts/psql.sh opens a session.

variable "postgres_sku" {
  description = "PostgreSQL Flexible Server SKU (POSTGRES_SKU)."
  type        = string
}

data "azuread_user" "deployer" {
  object_id = data.azurerm_client_config.current.object_id
}

# The deployer's public IP, for the hook and psql.
data "http" "deployer_ip" {
  url = "https://api.ipify.org"
}

module "postgres" {
  source                     = "./modules/postgres"
  name                       = "psql-${var.environment_name}-${local.token}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = var.location
  tags                       = local.tags
  sku_name                   = var.postgres_sku
  client_ip_address          = chomp(data.http.deployer_ip.response_body)
  private_endpoint_subnet_id = lookup(local.network.subnet_ids, "private-endpoints", null)
  private_dns_zone_ids       = local.network.private_dns_zone_ids

  administrator = {
    object_id      = data.azurerm_client_config.current.object_id
    principal_name = data.azuread_user.deployer.user_principal_name
    principal_type = "User"
  }
}

output "POSTGRES_SERVER_NAME" { value = module.postgres.name }
output "POSTGRES_HOST" { value = module.postgres.host }
