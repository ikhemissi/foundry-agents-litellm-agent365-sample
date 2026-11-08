# Public by default; given a private endpoint subnet, a private endpoint registered in the private DNS zone.

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id       = "00000000-0000-0000-0000-000000000001"
      subscription_id = "00000000-0000-0000-0000-000000000000"
    }
  }
}

variables {
  resource_group_name = "rg-test"
  location            = "francecentral"
  name                = "psql-test"
  client_ip_address   = "203.0.113.10"
}

run "public" {
  command = plan

  assert {
    condition     = length(azurerm_private_endpoint.main) == 0
    error_message = "No private endpoint without a subnet."
  }
  assert {
    condition     = length(azurerm_postgresql_flexible_server_firewall_rule.client) == 1
    error_message = "The client IP is let through the firewall."
  }
}

run "private_endpoint" {
  command = plan

  variables {
    private_endpoint_subnet_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test/subnets/private-endpoints"
    private_dns_zone_ids = {
      "privatelink.postgres.database.azure.com" = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Network/privateDnsZones/privatelink.postgres.database.azure.com"
    }
  }

  assert {
    condition     = length(azurerm_private_endpoint.main) == 1
    error_message = "A private endpoint in the given subnet."
  }
  assert {
    condition     = length(azurerm_postgresql_flexible_server_firewall_rule.client) == 1
    error_message = "The client IP is still let through while public access is on."
  }
}

run "private_only" {
  command = plan

  variables {
    public_network_access_enabled = false
  }

  assert {
    condition     = length(azurerm_postgresql_flexible_server_firewall_rule.azure_services) + length(azurerm_postgresql_flexible_server_firewall_rule.client) == 0
    error_message = "No firewall rules without public access."
  }
}
