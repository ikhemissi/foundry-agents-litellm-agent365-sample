# The expense policy MCP server: a container app (services/expense-policy-mcp, deployed by azd) serving Contoso's
# fictional expense policy, read-only and without user data. Internal ingress: only the apps of the Container Apps
# environment reach it, so it checks no token; LiteLLM admits the expense policy agent with that agent's own key.

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

resource "azurerm_container_app" "policy" {
  name                         = "ca-policy-mcp-${local.token}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_app_environment_id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  # azd finds the app of the expense-policy-mcp service through this tag.
  tags = merge(local.tags, { "azd-service-name" = "expense-policy-mcp" })

  identity {
    type         = "UserAssigned"
    identity_ids = [var.acr_pull_identity_id]
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
      name   = "expense-policy-mcp"
      image  = local.image_deployed ? var.image : local.placeholder_image
      cpu    = 0.25
      memory = "0.5Gi"

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
}
