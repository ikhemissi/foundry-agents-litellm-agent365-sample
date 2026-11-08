variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "address_space" {
  description = "The network's address range, e.g. 10.0.0.0/16."
  type        = string
}

variable "subnets" {
  description = "Subnets by name: their address range, and the service they are delegated to (e.g. Microsoft.App/environments), if any."
  type = map(object({
    address_prefix = string
    delegation     = optional(string)
  }))
}

variable "private_dns_zones" {
  description = "Private DNS zones to create and link to the network, e.g. privatelink.vaultcore.azure.net for Key Vault."
  type        = list(string)
  default     = []
}
