# Terraform Remote State Backend — Azure Storage
# Run bootstrap first to create the storage account and container.
# Note: Backend block does not support variable interpolation.

terraform {
  backend "azurerm" {
    resource_group_name  = "qualisys-tfstate-rg"
    storage_account_name = "qualisystfstate"
    container_name       = "tfstate"
    key                  = "infrastructure/terraform.tfstate"
  }
}
