# QUALISYS Azure Infrastructure — Outputs
# Unified output interface matching AWS outputs for CI/CD compatibility.

# =============================================================================
# Resource Group
# =============================================================================

output "resource_group_name" {
  description = "Name of the Azure resource group"
  value       = module.resource_group.resource_group_name
}

output "resource_group_id" {
  description = "ID of the Azure resource group"
  value       = module.resource_group.resource_group_id
}

# =============================================================================
# Networking
# =============================================================================

output "vnet_id" {
  description = "ID of the Virtual Network"
  value       = module.vnet.vnet_id
}

output "aks_subnet_id" {
  description = "ID of the AKS subnet"
  value       = module.vnet.aks_subnet_id
}

# =============================================================================
# AKS Cluster
# =============================================================================

output "cluster_name" {
  description = "Name of the AKS cluster"
  value       = module.aks.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint for the AKS cluster API server"
  value       = module.aks.cluster_endpoint
}

output "cluster_ca_certificate" {
  description = "Base64 encoded CA certificate for the cluster"
  value       = module.aks.cluster_ca_certificate
  sensitive   = true
}

output "kube_config_raw" {
  description = "Raw kubeconfig for the AKS cluster"
  value       = module.aks.kube_config_raw
  sensitive   = true
}

# =============================================================================
# PostgreSQL
# =============================================================================

output "postgresql_fqdn" {
  description = "Fully qualified domain name of the PostgreSQL server"
  value       = module.postgresql.fqdn
}

output "postgresql_server_id" {
  description = "ID of the PostgreSQL Flexible Server"
  value       = module.postgresql.server_id
}

# =============================================================================
# Redis
# =============================================================================

output "redis_hostname" {
  description = "Hostname of the Azure Cache for Redis"
  value       = module.redis.hostname
}

output "redis_port" {
  description = "SSL port of the Azure Cache for Redis"
  value       = module.redis.ssl_port
}

# =============================================================================
# Container Registry
# =============================================================================

output "acr_login_server" {
  description = "Login server URL for Azure Container Registry"
  value       = module.acr.login_server
}

output "acr_id" {
  description = "ID of the Azure Container Registry"
  value       = module.acr.acr_id
}

# =============================================================================
# Key Vault
# =============================================================================

output "key_vault_id" {
  description = "ID of the Azure Key Vault"
  value       = module.keyvault.key_vault_id
}

output "key_vault_uri" {
  description = "URI of the Azure Key Vault"
  value       = module.keyvault.key_vault_uri
}

# =============================================================================
# Monitoring
# =============================================================================

output "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace"
  value       = module.monitoring.log_analytics_workspace_id
}
