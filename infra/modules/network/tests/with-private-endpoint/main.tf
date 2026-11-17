# A project's network and a private endpoint in the same plan, as infra/network.tf wires them once a project uses a
# virtual network: the subnet's id is not known yet, and the plan must still succeed. The endpoint stands in for the
# catalog modules' own (count on whether private_endpoint is null), so that this test needs no other module: projects
# copy only the modules they use.

terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
  }
}

module "network" {
  source              = "../.."
  name                = "vnet-test"
  resource_group_name = "rg-test"
  location            = "francecentral"
  address_space       = "10.0.0.0/16"
  subnets = {
    private-endpoints = { address_prefix = "10.0.2.0/24" }
  }
  private_dns_zones = ["privatelink.vaultcore.azure.net"]
}

locals {
  private_endpoint = {
    subnet_id            = module.network.subnet_ids["private-endpoints"]
    private_dns_zone_ids = module.network.private_dns_zone_ids
  }
}

resource "azurerm_private_endpoint" "vault" {
  count               = local.private_endpoint == null ? 0 : 1
  name                = "pe-kv-test"
  resource_group_name = "rg-test"
  location            = "francecentral"
  subnet_id           = local.private_endpoint.subnet_id

  private_service_connection {
    name                           = "vault"
    private_connection_resource_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/kv-test"
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [local.private_endpoint.private_dns_zone_ids["privatelink.vaultcore.azure.net"]]
  }
}
