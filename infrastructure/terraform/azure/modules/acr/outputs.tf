output "acr_id" {
  description = "ID of the Azure Container Registry"
  value       = azurerm_container_registry.main.id
}

output "acr_name" {
  description = "Name of the Azure Container Registry"
  value       = azurerm_container_registry.main.name
}

output "login_server" {
  description = "Login server URL for the ACR"
  value       = azurerm_container_registry.main.login_server
}

output "admin_username" {
  description = "Admin username (if admin enabled)"
  value       = azurerm_container_registry.main.admin_username
}
