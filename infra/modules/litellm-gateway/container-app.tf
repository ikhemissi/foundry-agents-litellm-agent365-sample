# The gateway's container app: LiteLLM's stock image (no image to build) with its configuration and the collector's
# mounted from Container Apps secrets, an OpenTelemetry collector sidecar exporting with the managed identity, and
# health probes on LiteLLM's own endpoints.

resource "azurerm_container_app" "gateway" {
  name                         = var.name
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_apps_environment_id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.gateway.id]
  }

  secret {
    name                = "litellm-master-key"
    key_vault_secret_id = azurerm_key_vault_secret.master_key.versionless_id
    identity            = azurerm_user_assigned_identity.gateway.id
  }

  # Secret volumes are the simplest way to mount configuration files; these two hold no credentials. A secret volume
  # mounts every secret as a file named after it, so LiteLLM reads /etc/litellm/litellm-config (the admin key is
  # mounted too, as a file next to it: the same value the container already has in its environment).
  secret {
    name  = "litellm-config"
    value = local.litellm_config
  }

  secret {
    name  = "otel-config"
    value = file("${path.module}/otel-collector.yaml")
  }

  # Public HTTPS endpoint: clients and connected tools authenticate with LiteLLM keys.
  ingress {
    external_enabled = true
    target_port      = 4000
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # One replica: LiteLLM keeps some state in memory, and a spike or a demo needs no more.
    min_replicas = 1
    max_replicas = 1

    volume {
      name         = "secrets"
      storage_type = "Secret"
    }

    container {
      name   = "litellm"
      image  = local.litellm_image
      args   = ["--config", "/etc/litellm/litellm-config", "--port", "4000"]
      cpu    = 1.0
      memory = "2Gi"

      dynamic "env" {
        for_each = local.litellm_env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name        = "LITELLM_MASTER_KEY"
        secret_name = "litellm-master-key"
      }

      volume_mounts {
        name = "secrets"
        path = "/etc/litellm"
      }

      # The first start applies LiteLLM's database migrations: up to 5 minutes.
      startup_probe {
        transport               = "HTTP"
        port                    = 4000
        path                    = "/health/liveliness"
        interval_seconds        = 10
        failure_count_threshold = 30
      }

      liveness_probe {
        transport        = "HTTP"
        port             = 4000
        path             = "/health/liveliness"
        interval_seconds = 30
      }

      readiness_probe {
        transport        = "HTTP"
        port             = 4000
        path             = "/health/readiness"
        interval_seconds = 10
      }
    }

    container {
      name   = "otel-collector"
      image  = local.collector_image
      args   = ["--config=/etc/otelcol/otel-config"]
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.gateway.client_id
      }

      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = var.application_insights_connection_string
      }

      volume_mounts {
        name = "secrets"
        path = "/etc/otelcol"
      }

      liveness_probe {
        transport        = "HTTP"
        port             = 13133
        path             = "/"
        interval_seconds = 30
      }
    }
  }

  # The app resolves the admin key from Key Vault and calls Foundry from its first revision.
  depends_on = [
    azurerm_role_assignment.gateway_secrets,
    azurerm_role_assignment.gateway_foundry,
    azurerm_postgresql_flexible_server_database.gateway,
  ]
}
