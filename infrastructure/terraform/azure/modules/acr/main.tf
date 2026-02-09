# Azure Container Registry
# QUALISYS Azure Infrastructure — mirrors AWS ECR configuration
# Premium SKU with scanning, 3 repositories

resource "azurerm_container_registry" "main" {
  name                = replace("${var.project_name}${var.environment}acr", "-", "")
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.sku
  admin_enabled       = false

  # Geo-replication (Premium only, production)
  dynamic "georeplications" {
    for_each = var.environment == "production" && var.sku == "Premium" ? var.georeplications : []
    content {
      location                = georeplications.value.location
      zone_redundancy_enabled = georeplications.value.zone_redundancy
      tags                    = var.tags
    }
  }

  # Retention policy for untagged manifests
  retention_policy {
    days    = 7
    enabled = true
  }

  # Trust policy (content trust / image signing)
  trust_policy {
    enabled = var.environment == "production"
  }

  tags = var.tags
}

# =============================================================================
# Grant AKS pull access to ACR
# =============================================================================

resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = var.aks_principal_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.main.id
  skip_service_principal_aad_check = true
}
