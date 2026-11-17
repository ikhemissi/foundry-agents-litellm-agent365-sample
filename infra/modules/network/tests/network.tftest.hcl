# The subnets and private DNS zones a project lists, with their delegation and their link to the network.

mock_provider "azurerm" {
  # Key Vault, in the private endpoint run, needs a tenant id in UUID form.
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000001"
    }
  }
}

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
      jumpbox           = { address_prefix = "10.0.3.0/27", default_outbound_access = false }
      app-service       = { address_prefix = "10.0.4.0/26", delegation = "Microsoft.Web/serverFarms" }
    }
    private_dns_zones = ["privatelink.vaultcore.azure.net"]
  }

  assert {
    condition     = output.subnet_address_prefixes["jumpbox"] == "10.0.3.0/27"
    error_message = "Each subnet's address prefix is an output, known at plan time."
  }

  assert {
    condition     = azurerm_subnet.main["container-apps"].delegation[0].service_delegation[0].name == "Microsoft.App/environments"
    error_message = "The container-apps subnet is delegated to Container Apps."
  }
  assert {
    condition     = azurerm_subnet.main["container-apps"].delegation[0].service_delegation[0].actions == toset(["Microsoft.Network/virtualNetworks/subnets/join/action"])
    error_message = "Container Apps delegations declare the join action."
  }
  assert {
    condition     = azurerm_subnet.main["app-service"].delegation[0].service_delegation[0].actions == toset(["Microsoft.Network/virtualNetworks/subnets/action"])
    error_message = "App Service plan delegations declare the action Azure records for them, so that plans stay clean."
  }
  assert {
    condition     = length(azurerm_subnet.main["private-endpoints"].delegation) == 0
    error_message = "A subnet without a delegation has none."
  }
  assert {
    condition     = azurerm_subnet.main["jumpbox"].default_outbound_access_enabled == false
    error_message = "A subnet can be made private (no default outbound access)."
  }
  assert {
    condition     = length(azurerm_private_dns_zone_virtual_network_link.main) == 1
    error_message = "Each private DNS zone is linked to the network."
  }
}

# A network and a module's private endpoint in one plan (tests/with-private-endpoint): the subnet's id is unknown until
# apply, and the plan succeeds because the modules decide on the private endpoint from an object, not from that id.
run "private_endpoint_in_the_same_plan" {
  command = plan

  module {
    source = "./tests/with-private-endpoint"
  }

  providers = {
    azurerm = azurerm
  }
}
