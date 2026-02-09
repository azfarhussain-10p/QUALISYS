output "server_id" {
  description = "ID of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.main.id
}

output "server_name" {
  description = "Name of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.main.name
}

output "fqdn" {
  description = "Fully qualified domain name of the PostgreSQL server"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "database_name" {
  description = "Name of the primary database"
  value       = azurerm_postgresql_flexible_server_database.main.name
}

output "admin_username" {
  description = "Administrator username"
  value       = azurerm_postgresql_flexible_server.main.administrator_login
}

output "admin_password_secret_id" {
  description = "Key Vault secret ID for admin password"
  value       = azurerm_key_vault_secret.postgresql_admin_password.id
  sensitive   = true
}

output "connection_string_secret_id" {
  description = "Key Vault secret ID for connection string"
  value       = azurerm_key_vault_secret.postgresql_connection_string.id
  sensitive   = true
}
