# azd passes every value of main.tfvars.json as a string, empty when the azd environment does not set it. Every value
# except LITELLM_IMAGE comes from the layers this one depends on (azure-platform, foundry-model, postgres).

variable "environment_name" {
  description = "azd environment name (AZURE_ENV_NAME)."
  type        = string
}

variable "subscription_id" {
  description = "Target subscription (AZURE_SUBSCRIPTION_ID)."
  type        = string
}

variable "location" {
  description = "Region (AZURE_LOCATION)."
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

variable "container_app_environment_id" {
  description = "Container Apps environment of the platform layer (AZURE_CONTAINER_APPS_ENVIRONMENT_ID)."
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault of the platform layer (PLATFORM_KEY_VAULT_ID), where the gateway's admin key is kept."
  type        = string
}

variable "application_insights_id" {
  description = "Application Insights of the platform layer (PLATFORM_APPLICATION_INSIGHTS_ID)."
  type        = string
}

variable "application_insights_connection_string" {
  description = "Its connection string (PLATFORM_APPLICATION_INSIGHTS_CONNECTION_STRING); locates the resource, ingestion still requires Entra."
  type        = string
  sensitive   = true
}

variable "foundry_account_id" {
  description = "Foundry account of the foundry-model layer (FOUNDRY_ACCOUNT_ID)."
  type        = string

  validation {
    condition     = var.foundry_account_id != ""
    error_message = "FOUNDRY_ACCOUNT_ID is empty: provision the foundry-model layer first."
  }
}

variable "foundry_openai_endpoint" {
  description = "Its OpenAI-compatible endpoint (FOUNDRY_OPENAI_ENDPOINT)."
  type        = string
}

variable "model_deployment_name" {
  description = "The chat model deployment (FOUNDRY_MODEL_DEPLOYMENT_NAME), exposed by the gateway under the same name."
  type        = string
}

variable "postgres_server_id" {
  description = "PostgreSQL server of the postgres layer (POSTGRES_SERVER_ID); the gateway's database is created on it."
  type        = string

  validation {
    condition     = var.postgres_server_id != ""
    error_message = "POSTGRES_SERVER_ID is empty: provision the postgres layer first."
  }
}

variable "postgres_host" {
  description = "Its host name (POSTGRES_HOST)."
  type        = string
}

variable "litellm_image" {
  description = "LiteLLM image (LITELLM_IMAGE), pinned by digest. Empty: the version tested with this block (main.tf)."
  type        = string
  default     = ""
}
