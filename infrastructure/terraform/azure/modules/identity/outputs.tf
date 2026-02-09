output "devops_group_id" {
  description = "Object ID of the DevOps Azure AD group"
  value       = azuread_group.devops.object_id
}

output "developers_group_id" {
  description = "Object ID of the Developers Azure AD group"
  value       = azuread_group.developers.object_id
}

output "cicd_group_id" {
  description = "Object ID of the CI/CD Azure AD group"
  value       = azuread_group.cicd.object_id
}

output "external_secrets_identity_client_id" {
  description = "Client ID of the ExternalSecrets managed identity"
  value       = azurerm_user_assigned_identity.external_secrets.client_id
}

output "external_secrets_identity_id" {
  description = "Resource ID of the ExternalSecrets managed identity"
  value       = azurerm_user_assigned_identity.external_secrets.id
}

output "app_workload_identity_client_id" {
  description = "Client ID of the app workload managed identity"
  value       = azurerm_user_assigned_identity.app_workload.client_id
}

output "app_workload_identity_id" {
  description = "Resource ID of the app workload managed identity"
  value       = azurerm_user_assigned_identity.app_workload.id
}
