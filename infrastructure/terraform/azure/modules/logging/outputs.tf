# Outputs for QUALISYS Logging Module (Azure)
# Story: 0-20 Log Aggregation

output "workspace_id_staging" {
  description = "Log Analytics workspace ID for staging"
  value       = azurerm_log_analytics_workspace.staging.id
}

output "workspace_id_production" {
  description = "Log Analytics workspace ID for production"
  value       = azurerm_log_analytics_workspace.production.id
}

output "workspace_customer_id_staging" {
  description = "Log Analytics workspace customer ID (workspace ID) for staging"
  value       = azurerm_log_analytics_workspace.staging.workspace_id
}

output "workspace_customer_id_production" {
  description = "Log Analytics workspace customer ID (workspace ID) for production"
  value       = azurerm_log_analytics_workspace.production.workspace_id
}

output "workspace_primary_key_staging" {
  description = "Log Analytics primary shared key for staging"
  value       = azurerm_log_analytics_workspace.staging.primary_shared_key
  sensitive   = true
}

output "workspace_primary_key_production" {
  description = "Log Analytics primary shared key for production"
  value       = azurerm_log_analytics_workspace.production.primary_shared_key
  sensitive   = true
}

output "fluent_bit_identity_client_id" {
  description = "Managed Identity client ID for Fluent Bit Workload Identity"
  value       = azurerm_user_assigned_identity.fluent_bit.client_id
}

output "action_group_id" {
  description = "Action Group ID for log-based alerts"
  value       = azurerm_monitor_action_group.log_alerts.id
}
