variable "name" {
  description = "Globally unique."
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

variable "sku_name" {
  description = "Server SKU; the default is burstable, for development."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "administrator" {
  description = "The Entra administrator, who creates the workloads' roles (in development, the deploying user). Null: none."
  type = object({
    object_id      = string
    principal_name = string
    principal_type = string # User, Group or ServicePrincipal
  })
  default = null
}

variable "allow_azure_services" {
  description = "Open the firewall to Azure services (Container Apps outside a virtual network have no fixed outbound IP)."
  type        = bool
  default     = true
}

variable "client_ip_address" {
  description = "One public IP address allowed through the firewall, e.g. the deployer's for psql. Null: none."
  type        = string
  default     = null
}

variable "public_network_access_enabled" {
  description = "False once every client reaches the server through the virtual network."
  type        = bool
  default     = true
}

variable "private_endpoint_subnet_id" {
  description = "Subnet for a private endpoint. Null: none."
  type        = string
  default     = null
}

variable "private_dns_zone_ids" {
  description = "Private DNS zone ids by zone name (the network module's output); privatelink.postgres.database.azure.com is used."
  type        = map(string)
  default     = {}
}
