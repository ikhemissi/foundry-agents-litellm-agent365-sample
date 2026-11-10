# The secrets that cannot be avoided (e.g. a gateway's keys, an app registration's client secret). The deployer writes
# them (Terraform and the project's scripts); each workload reads only its own.

module "key_vault" {
  source                     = "./modules/key-vault"
  name                       = "kv-${substr(var.environment_name, 0, 10)}-${local.token}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = var.location
  tags                       = local.tags
  secrets_officer_object_ids = [data.azurerm_client_config.current.object_id]
  private_endpoint_subnet_id = lookup(local.network.subnet_ids, "private-endpoints", null)
  private_dns_zone_ids       = local.network.private_dns_zone_ids
}

output "KEY_VAULT_ID" { value = module.key_vault.id }
output "KEY_VAULT_NAME" { value = module.key_vault.name }
output "KEY_VAULT_URI" { value = module.key_vault.uri }
