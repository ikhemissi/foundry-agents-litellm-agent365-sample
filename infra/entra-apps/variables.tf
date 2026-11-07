# azd passes every value of main.tfvars.json as a string, empty when the azd environment does not set it.

variable "environment_name" {
  description = "azd environment name (AZURE_ENV_NAME)."
  type        = string
}

variable "subscription_id" {
  description = "Target subscription (AZURE_SUBSCRIPTION_ID)."
  type        = string
}

variable "key_vault_id" {
  description = "The platform's Key Vault (PLATFORM_KEY_VAULT_ID), where the gateway app's client secret is kept."
  type        = string

  validation {
    condition     = var.key_vault_id != ""
    error_message = "PLATFORM_KEY_VAULT_ID is empty: provision the azure-platform layer first."
  }
}

variable "chat_ui_client_id" {
  description = "The chat UI's app registration (CHAT_UI_CLIENT_ID), pre-authorized to request gateway tokens for its users. Empty until the chat-ui layer exists."
  type        = string
  default     = ""
}
