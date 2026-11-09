# The gateway: LiteLLM's stock image pinned by digest, one replica, its admin key only in Key Vault, keyless calls to
# Foundry with its own identity, its own database, and traces without prompts or completions.

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      subscription_id = "00000000-0000-0000-0000-000000000000"
    }
  }

  # IDs in the shape the provider validates on apply.
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-ca-litellm-test"
      client_id    = "00000000-0000-4000-8000-000000000003"
      principal_id = "00000000-0000-4000-8000-000000000004"
    }
  }

  mock_resource "azurerm_key_vault_secret" {
    defaults = {
      versionless_id = "https://kv-test.vault.azure.net/secrets/litellm-master-key"
    }
  }
}

mock_provider "random" {}

variables {
  name                                   = "ca-litellm-test"
  resource_group_name                    = "rg-test"
  location                               = "francecentral"
  container_apps_environment_id          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.App/managedEnvironments/cae-test"
  key_vault_id                           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/kv-test"
  application_insights_id                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Insights/components/appi-test"
  application_insights_connection_string = "InstrumentationKey=00000000-0000-0000-0000-000000000002"
  foundry_account_id                     = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.CognitiveServices/accounts/ais-test"
  foundry_openai_endpoint                = "https://ais-test.openai.azure.com/"
  model_deployment_name                  = "gpt-test"
  postgres_server_id                     = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.DBforPostgreSQL/flexibleServers/psql-test"
  postgres_host                          = "psql-test.postgres.database.azure.com"
}

# Applied with the mock providers (nothing is created): the container's settings are known only after apply.
run "defaults" {
  command = apply

  assert {
    condition     = strcontains(azurerm_container_app.gateway.template[0].container[0].image, "@sha256:")
    error_message = "The default LiteLLM image is pinned by digest."
  }
  assert {
    condition     = azurerm_container_app.gateway.template[0].min_replicas == 1 && azurerm_container_app.gateway.template[0].max_replicas == 1
    error_message = "One replica: LiteLLM keeps some state in memory."
  }
  assert {
    condition     = azurerm_key_vault_secret.master_key.name == "litellm-master-key" && azurerm_key_vault_secret.master_key.key_vault_id == var.key_vault_id
    error_message = "The admin key is kept in Key Vault."
  }
  assert {
    condition     = endswith(azurerm_role_assignment.gateway_foundry.role_definition_id, "53ca6127-db72-4b80-b1b0-d745d6d5456d") && azurerm_role_assignment.gateway_foundry.scope == var.foundry_account_id
    error_message = "The gateway calls Foundry with its own identity (Foundry User on the account)."
  }
  assert {
    condition     = azurerm_postgresql_flexible_server_database.gateway.name == "litellm"
    error_message = "The gateway has its own database on the server."
  }
  assert {
    condition     = contains([for env in azurerm_container_app.gateway.template[0].container[0].env : env.name if env.value == "NO_CONTENT"], "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT")
    error_message = "Traces carry no prompts or completions."
  }
}

run "another_image" {
  command = plan

  variables {
    image = "ghcr.io/berriai/litellm-database:test@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }

  assert {
    condition     = azurerm_container_app.gateway.template[0].container[0].image == var.image
    error_message = "The image can be replaced, e.g. to try a newer LiteLLM."
  }
}
