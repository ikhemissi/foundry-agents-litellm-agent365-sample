variable "name" {
  description = "The container app's name; its identity is id-<name>."
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

variable "container_apps_environment_id" {
  type = string
}

variable "key_vault_id" {
  description = "Where the gateway's admin key is kept."
  type        = string
}

variable "application_insights_id" {
  type = string
}

variable "application_insights_connection_string" {
  type      = string
  sensitive = true
}

variable "foundry_account_id" {
  description = "The gateway's identity gets the Foundry User role on this account."
  type        = string
}

variable "foundry_openai_endpoint" {
  type = string
}

variable "model_deployment_name" {
  description = "The chat model deployment, exposed by the gateway under the same name."
  type        = string
}

variable "postgres_server_id" {
  description = "The gateway's database is created on this server."
  type        = string
}

variable "postgres_host" {
  type = string
}

variable "image" {
  description = "LiteLLM image, pinned by digest. Empty: the version tested with this module (main.tf)."
  type        = string
  default     = ""
}
