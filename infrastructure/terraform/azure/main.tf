# QUALISYS Azure Infrastructure — Root Module
# This file composes all Azure modules for the QUALISYS platform.

locals {
  common_tags = {
    Project     = "QUALISYS"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "DevOps"
    Cloud       = "Azure"
  }
}

# =============================================================================
# Resource Group
# =============================================================================

module "resource_group" {
  source = "./modules/resource-group"

  project_name = var.project_name
  environment  = var.environment
  location     = var.azure_location
  tags         = local.common_tags
}

# =============================================================================
# Virtual Network
# =============================================================================

module "vnet" {
  source = "./modules/vnet"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.azure_location
  resource_group_name = module.resource_group.resource_group_name
  address_space       = var.vnet_address_space
  tags                = local.common_tags
}

# =============================================================================
# Azure Kubernetes Service
# =============================================================================

module "aks" {
  source = "./modules/aks"

  project_name          = var.project_name
  environment           = var.environment
  location              = var.azure_location
  resource_group_name   = module.resource_group.resource_group_name
  resource_group_id     = module.resource_group.resource_group_id
  kubernetes_version    = var.kubernetes_version
  vnet_subnet_id        = module.vnet.aks_subnet_id
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id

  general_node_vm_size    = var.general_node_vm_size
  general_node_min_count  = var.general_node_min_count
  general_node_max_count  = var.general_node_max_count
  playwright_node_vm_size   = var.playwright_node_vm_size
  playwright_node_min_count = var.playwright_node_min_count
  playwright_node_max_count = var.playwright_node_max_count

  tags = local.common_tags
}

# =============================================================================
# Azure Database for PostgreSQL Flexible Server
# =============================================================================

module "postgresql" {
  source = "./modules/postgresql"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.azure_location
  resource_group_name = module.resource_group.resource_group_name
  delegated_subnet_id = module.vnet.postgresql_subnet_id
  private_dns_zone_id = module.vnet.postgresql_private_dns_zone_id
  postgresql_version  = var.postgresql_version
  sku_name            = var.postgresql_sku_name
  storage_mb          = var.postgresql_storage_mb
  db_name             = var.postgresql_db_name
  admin_username      = var.postgresql_admin_username
  key_vault_id        = module.keyvault.key_vault_id
  tags                = local.common_tags
}

# =============================================================================
# Azure Cache for Redis
# =============================================================================

module "redis" {
  source = "./modules/redis"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.azure_location
  resource_group_name = module.resource_group.resource_group_name
  subnet_id           = module.vnet.redis_subnet_id
  capacity            = var.redis_capacity
  family              = var.redis_family
  sku_name            = var.redis_sku_name
  key_vault_id        = module.keyvault.key_vault_id
  tags                = local.common_tags
}

# =============================================================================
# Azure Container Registry
# =============================================================================

module "acr" {
  source = "./modules/acr"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.azure_location
  resource_group_name = module.resource_group.resource_group_name
  sku                 = var.acr_sku
  aks_principal_id    = module.aks.kubelet_identity_object_id
  tags                = local.common_tags
}

# =============================================================================
# Azure Key Vault
# =============================================================================

module "keyvault" {
  source = "./modules/keyvault"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.azure_location
  resource_group_name = module.resource_group.resource_group_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  recovery_days       = var.secret_recovery_days
  tags                = local.common_tags
}

# =============================================================================
# Azure AD & Managed Identities
# =============================================================================

module "identity" {
  source = "./modules/identity"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.azure_location
  resource_group_name = module.resource_group.resource_group_name
  resource_group_id   = module.resource_group.resource_group_id
  aks_oidc_issuer_url = module.aks.oidc_issuer_url
  key_vault_id        = module.keyvault.key_vault_id
  acr_id              = module.acr.acr_id
  tags                = local.common_tags
}

# =============================================================================
# Azure Monitor & Log Analytics
# =============================================================================

module "monitoring" {
  source = "./modules/monitoring"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.azure_location
  resource_group_name = module.resource_group.resource_group_name
  log_retention_days  = var.log_retention_days
  budget_alert_email  = var.budget_alert_email
  tags                = local.common_tags
}
