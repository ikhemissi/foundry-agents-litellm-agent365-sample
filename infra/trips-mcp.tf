# The trips MCP server (services/trips-mcp, deployed by azd): each user's fictional trips and expenses, in tables of
# its own storage account reached with its managed identity. Internal ingress: only apps of the environment reach it
# (LiteLLM). Every tool call must carry the user's token for the gateway app, which LiteLLM passes on; discovery
# (initialize, tools/list) needs none (services/trips-mcp/user_auth.py).

variable "trips_mcp_image" {
  description = "The image azd deployed (SERVICE_TRIPS_MCP_IMAGE_NAME). Empty before the first deployment."
  type        = string
}

module "trips_storage" {
  source                     = "./modules/storage-account"
  name                       = "sttrips${local.token}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = var.location
  tags                       = local.tags
  private_endpoint_subnet_id = lookup(local.network.subnet_ids, "private-endpoints", null)
  private_endpoint_services  = ["table"]
  private_dns_zone_ids       = local.network.private_dns_zone_ids
}

module "trips_mcp" {
  source                        = "./modules/container-app"
  name                          = "ca-trips-mcp-${local.token}"
  azd_service_name              = "trips-mcp"
  image                         = var.trips_mcp_image
  port                          = 8080
  resource_group_name           = azurerm_resource_group.main.name
  location                      = var.location
  tags                          = local.tags
  container_apps_environment_id = module.container_apps_environment.id
  registry_server               = module.container_registry.login_server
  registry_pull_identity_id     = module.container_registry.pull_identity_id

  env = {
    TRIPS_TABLE_ENDPOINT = module.trips_storage.primary_table_endpoint
    TRIPS_AUTH_TENANT_ID = data.azurerm_client_config.current.tenant_id
    TRIPS_AUTH_AUDIENCE  = azuread_application_identifier_uri.gateway.identifier_uri
    TRIPS_AUTH_SCOPE     = local.gateway_scope
  }

  role_assignments = {
    tables = { scope = module.trips_storage.id, role = "Storage Table Data Contributor" }
  }
}

# Resolves only inside the Container Apps environment (LiteLLM).
output "TRIPS_MCP_URL" { value = "${module.trips_mcp.url}/mcp" }
