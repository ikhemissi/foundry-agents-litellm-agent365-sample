# azd passes every value of main.tfvars.json as a string, empty when the azd environment does not set it.

variable "environment_name" {
  description = "azd environment name (AZURE_ENV_NAME)."
  type        = string
}

variable "subscription_id" {
  description = "Target subscription (AZURE_SUBSCRIPTION_ID)."
  type        = string
}

variable "location" {
  description = "Region of the server (AZURE_LOCATION)."
  type        = string
  default     = "francecentral"
}

variable "tags" {
  description = "Extra tags, as comma-separated key=value pairs (RESOURCE_TAGS). Empty: none."
  type        = string
  default     = ""
}

variable "resource_group_name" {
  description = "Resource group of the platform layer (AZURE_RESOURCE_GROUP)."
  type        = string

  validation {
    condition     = var.resource_group_name != ""
    error_message = "AZURE_RESOURCE_GROUP is empty: provision the azure-platform layer first."
  }
}

variable "postgres_sku" {
  description = "PostgreSQL Flexible Server SKU (POSTGRES_SKU). Empty: B_Standard_B1ms (burstable, dev)."
  type        = string
  default     = ""
}

variable "deployer_is_user" {
  description = "The deploying principal is a user and becomes the server's Entra administrator, to create the workloads' roles and use psql (dev only; set false in automation and make a dedicated identity the administrator)."
  type        = bool
  default     = true
}

variable "allow_deployer_ip" {
  description = "Open the firewall to the deployer's public IP for the hooks and psql (dev only)."
  type        = bool
  default     = true
}
