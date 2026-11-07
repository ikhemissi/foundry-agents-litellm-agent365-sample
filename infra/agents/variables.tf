# azd passes every value of main.tfvars.json as a string, empty when the azd environment does not set it.

variable "environment_name" {
  description = "azd environment name (AZURE_ENV_NAME)."
  type        = string
}

variable "subscription_id" {
  description = "Target subscription (AZURE_SUBSCRIPTION_ID)."
  type        = string
}

variable "foundry_account_id" {
  description = "The Foundry account of the foundry-model layer (FOUNDRY_ACCOUNT_ID)."
  type        = string

  validation {
    condition     = var.foundry_account_id != ""
    error_message = "FOUNDRY_ACCOUNT_ID is empty: provision the foundry-model layer first."
  }
}

variable "foundry_project_endpoint" {
  description = "The Foundry project's endpoint (FOUNDRY_PROJECT_ENDPOINT)."
  type        = string
}
