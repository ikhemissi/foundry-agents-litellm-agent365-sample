# LiteLLM, the AI gateway every model, MCP and A2A call goes through. Terraform creates the gateway; the postprovision
# hook gives its identity a database role, then configures it through its admin API (src/configure_gateway.py: the
# trips MCP server, the expense policy agent, one key per agent, the Agent 365 guardrail).

variable "litellm_image" {
  description = "LiteLLM image, pinned by digest (LITELLM_IMAGE). Empty: the version tested with the module."
  type        = string
}

module "litellm" {
  source                                 = "./modules/litellm-gateway"
  name                                   = "ca-litellm-${local.token}"
  image                                  = var.litellm_image
  resource_group_name                    = azurerm_resource_group.main.name
  location                               = var.location
  tags                                   = local.tags
  container_apps_environment_id          = module.container_apps_environment.id
  key_vault_id                           = module.key_vault.id
  application_insights_id                = module.monitoring.application_insights_id
  application_insights_connection_string = module.monitoring.application_insights_connection_string
  foundry_account_id                     = module.foundry.account_id
  foundry_openai_endpoint                = module.foundry.openai_endpoint
  model_deployment_name                  = module.foundry.model_deployment_name
  postgres_server_id                     = module.postgres.id
  postgres_host                          = module.postgres.host
}

output "LITELLM_URL" { value = module.litellm.url }
output "LITELLM_APP_NAME" { value = module.litellm.app_name }
output "LITELLM_IDENTITY_NAME" { value = module.litellm.identity_name }
output "LITELLM_IDENTITY_PRINCIPAL_ID" { value = module.litellm.identity_principal_id }
output "LITELLM_DATABASE_NAME" { value = module.litellm.database_name }
output "LITELLM_MASTER_KEY_SECRET_NAME" { value = module.litellm.master_key_secret_name }
