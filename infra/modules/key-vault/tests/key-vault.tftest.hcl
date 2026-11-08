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
  name                = "kv-test"
}

run "public" {
  command = plan

  assert {
    condition     = length(azurerm_private_endpoint.main) == 0
    error_message = "No private endpoint without a subnet."
  }
}

run "private_endpoint" {
  command = plan

  variables {
    private_endpoint_subnet_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test/subnets/private-endpoints"
    private_dns_zone_ids = {
      "privatelink.vaultcore.azure.net" = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Network/privateDnsZones/privatelink.vaultcore.azure.net"
    }
  }

  assert {
    condition     = length(azurerm_private_endpoint.main) == 1
    error_message = "A private endpoint in the given subnet."
  }
}
