# The subnets and private DNS zones a project lists, with their delegation and their link to the network.

mock_provider "azurerm" {}

run "subnets_and_zones" {
  command = plan

  variables {
    name                = "vnet-test"
    resource_group_name = "rg-test"
    location            = "francecentral"
    address_space       = "10.0.0.0/16"
    subnets = {
      container-apps    = { address_prefix = "10.0.0.0/23", delegation = "Microsoft.App/environments" }
      private-endpoints = { address_prefix = "10.0.2.0/24" }
    }
    private_dns_zones = ["privatelink.vaultcore.azure.net"]
  }

  assert {
    condition     = azurerm_subnet.main["container-apps"].delegation[0].service_delegation[0].name == "Microsoft.App/environments"
    error_message = "The container-apps subnet is delegated to Container Apps."
  }
  assert {
    condition     = length(azurerm_subnet.main["private-endpoints"].delegation) == 0
    error_message = "A subnet without a delegation has none."
  }
  assert {
    condition     = length(azurerm_private_dns_zone_virtual_network_link.main) == 1
    error_message = "Each private DNS zone is linked to the network."
  }
}
