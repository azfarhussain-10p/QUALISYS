output "redis_id" {
  description = "ID of the Azure Cache for Redis"
  value       = azurerm_redis_cache.main.id
}

output "hostname" {
  description = "Hostname of the Redis cache"
  value       = azurerm_redis_cache.main.hostname
}

output "ssl_port" {
  description = "SSL port of the Redis cache"
  value       = azurerm_redis_cache.main.ssl_port
}

output "primary_access_key" {
  description = "Primary access key for Redis"
  value       = azurerm_redis_cache.main.primary_access_key
  sensitive   = true
}

output "primary_connection_string" {
  description = "Primary connection string for Redis"
  value       = azurerm_redis_cache.main.primary_connection_string
  sensitive   = true
}

output "redis_primary_key_secret_id" {
  description = "Key Vault secret ID for Redis primary key"
  value       = azurerm_key_vault_secret.redis_primary_key.id
  sensitive   = true
}
