terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.10"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.5"
    }
  }

  # Remote state in an Entra-authenticated storage account, one key per layer (provider.conf.json).
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  subscription_id     = var.subscription_id
  storage_use_azuread = true
}

provider "azuread" {}
