# LiteLLM gateway: the LiteLLM proxy on Container Apps with its own managed identity, calling the Foundry model
# without keys, keeping its state (keys, teams, MCP servers, guardrails, spend logs) in its own PostgreSQL database
# with an Entra token, and exporting traces to Application Insights through an OpenTelemetry collector sidecar.
# Project-specific settings (MCP servers, teams, virtual keys, guardrails) go through LiteLLM's admin API or UI into the
# database, so this module's files stay as they are.

data "azurerm_client_config" "current" {}

locals {
  # The "-database" variant ships the Prisma client LiteLLM needs for its database. Pinned by digest: update both
  # together, and read the release notes (auth and MCP behaviour change often).
  litellm_image   = coalesce(var.image, "ghcr.io/berriai/litellm-database:v1.106.6@sha256:7ef0e78fe00ad5ea7ea45666cc1d1f02cb7076aee69091543bf397de52db33ce")
  collector_image = "otel/opentelemetry-collector-contrib:0.162.0"
  database_name   = "litellm"
  # "Foundry User" (formerly "Azure AI User"): calls to any Foundry model, not only Azure OpenAI ones.
  foundry_user_role_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"

  litellm_config = templatefile("${path.module}/config.yaml.tftpl", {
    model_deployment_name = var.model_deployment_name
    openai_endpoint       = var.foundry_openai_endpoint
  })

  litellm_env = {
    # The managed identity signs in to Foundry and to PostgreSQL.
    AZURE_CLIENT_ID = azurerm_user_assigned_identity.gateway.client_id
    # LiteLLM builds its database URL from these and uses an Entra token as the password. DATABASE_USER, not its alias
    # DATABASE_USERNAME: the token refresh (before the hourly expiry) reads only DATABASE_USER.
    AZURE_POSTGRESQL_AUTH = "true"
    DATABASE_HOST         = var.postgres_host
    DATABASE_PORT         = "5432"
    DATABASE_NAME         = local.database_name
    DATABASE_USER         = azurerm_user_assigned_identity.gateway.name
    DATABASE_SSLMODE      = "require"
    # Use the bundled model cost map instead of downloading it at startup, and send no usage telemetry to LiteLLM.
    LITELLM_LOCAL_MODEL_COST_MAP = "True"
    LITELLM_TELEMETRY            = "False"
    OTEL_EXPORTER                = "otlp_http"
    OTEL_ENDPOINT                = "http://127.0.0.1:4318/v1/traces"
    OTEL_SERVICE_NAME            = "litellm-gateway"
    # Traces carry model, tokens and latency, not prompts or completions.
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT = "NO_CONTENT"
  }
}

resource "azurerm_user_assigned_identity" "gateway" {
  name                = "id-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "gateway_foundry" {
  scope              = var.foundry_account_id
  role_definition_id = local.foundry_user_role_id
  principal_id       = azurerm_user_assigned_identity.gateway.principal_id
  principal_type     = "ServicePrincipal"
}

# Application Insights has local authentication disabled: the collector ingests with this role.
resource "azurerm_role_assignment" "gateway_metrics" {
  scope                = var.application_insights_id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_user_assigned_identity.gateway.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "gateway_secrets" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.gateway.principal_id
  principal_type       = "ServicePrincipal"
}

# LiteLLM's admin key: the UI login, the admin API and connecting the gateway to other tools. LiteLLM requires the "sk-"
# prefix. It is in the Terraform state (Entra-protected storage) and in Key Vault; never in azd values or files.
resource "random_password" "master_key" {
  length  = 48
  special = false
}

resource "azurerm_key_vault_secret" "master_key" {
  name         = "litellm-master-key"
  value        = "sk-${random_password.master_key.result}"
  key_vault_id = var.key_vault_id
}

resource "azurerm_postgresql_flexible_server_database" "gateway" {
  name      = local.database_name
  server_id = var.postgres_server_id
  charset   = "UTF8"
  collation = "en_US.utf8"
}
