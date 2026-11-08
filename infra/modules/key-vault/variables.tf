variable "name" {
  description = "Globally unique, 3 to 24 characters."
  type        = string
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

variable "secrets_officer_object_ids" {
  description = "Principals that write secrets (Key Vault Secrets Officer), e.g. the deployer, since Terraform writes the secrets it generates."
  type        = list(string)
  default     = []
}

variable "public_network_access_enabled" {
  description = "False once every client reaches the vault through the virtual network (the deployer included)."
  type        = bool
  default     = true
}

variable "private_endpoint_subnet_id" {
  description = "Subnet for a private endpoint. Null: none."
  type        = string
  default     = null
}

variable "private_dns_zone_ids" {
  description = "Private DNS zone ids by zone name (the network module's output); privatelink.vaultcore.azure.net is used."
  type        = map(string)
  default     = {}
}
