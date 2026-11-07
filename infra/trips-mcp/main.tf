# The trips MCP server: a container app (services/trips-mcp, deployed by azd) with each user's trips and expenses in
# tables of its own storage account, reached with its managed identity. Internal ingress: only the apps of the
# Container Apps environment reach it (LiteLLM). It also checks every request's user token: issued in this tenant,
# for the trips API (TRIPS_API_AUDIENCE), with the delegated scope Trips.ReadWrite (services/trips-mcp/user_auth.py).

data "azurerm_client_config" "current" {}

locals {
  token = substr(sha1("${var.subscription_id}-${var.environment_name}"), 0, 8)

  extra_tag_pairs = [for pair in split(",", var.tags) : split("=", pair) if trimspace(pair) != ""]
  extra_tags = {
    for pair in local.extra_tag_pairs : trimspace(pair[0]) => trimspace(join("=", slice(pair, 1, length(pair))))
  }
  tags = merge(local.extra_tags, { "azd-env-name" = var.environment_name })

  # Until azd deploys the service, the app runs a placeholder image listening on port 80; the postdeploy hook of the
  # service provisions this layer again to switch to the real port and add the health probe.
  placeholder_image = "mcr.microsoft.com/k8se/quickstart:latest"
  image_deployed    = var.image != ""
  port              = 8080
}

resource "azurerm_storage_account" "trips" {
  name                            = "sttrips${local.token}"
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = true
  tags                            = local.tags
}

resource "azurerm_user_assigned_identity" "trips" {
  name                = "id-trips-mcp-${local.token}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = local.tags
}

resource "azurerm_role_assignment" "trips_tables" {
  scope                = azurerm_storage_account.trips.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.trips.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_container_app" "trips" {
  name                         = "ca-trips-mcp-${local.token}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_app_environment_id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  # azd finds the app of the trips-mcp service through this tag.
  tags = merge(local.tags, { "azd-service-name" = "trips-mcp" })

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.trips.id, var.acr_pull_identity_id]
  }

  registry {
    server   = var.registry_server
    identity = var.acr_pull_identity_id
  }

  ingress {
    external_enabled = false
    target_port      = local.image_deployed ? local.port : 80
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "trips-mcp"
      image  = local.image_deployed ? var.image : local.placeholder_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.trips.client_id
      }

      env {
        name  = "TRIPS_TABLE_ENDPOINT"
        value = azurerm_storage_account.trips.primary_table_endpoint
      }

      env {
        name  = "TRIPS_AUTH_TENANT_ID"
        value = data.azurerm_client_config.current.tenant_id
      }

      env {
        name  = "TRIPS_AUTH_AUDIENCE"
        value = var.trips_api_audience
      }

      dynamic "readiness_probe" {
        for_each = local.image_deployed ? [1] : []
        content {
          transport        = "HTTP"
          port             = local.port
          path             = "/health"
          interval_seconds = 10
        }
      }
    }
  }

  lifecycle {
    # azd deploy changes the image between two provisions; the next provision passes the same image back.
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.trips_tables]
}
