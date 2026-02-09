# Azure Cache for Redis
# QUALISYS Azure Infrastructure — mirrors AWS ElastiCache Redis configuration
# Premium tier with TLS, clustering support

locals {
  is_production = var.environment == "production"
  is_dev        = var.environment == "dev"

  # Capacity: dev=0 (250MB), staging=1 (6GB), production=2 (13GB)
  redis_capacity = (
    var.capacity > 0
    ? var.capacity
    : (local.is_production ? 2 : (local.is_dev ? 0 : 1))
  )

  # SKU: dev=Standard, staging/production=Premium
  redis_sku    = local.is_dev ? "Standard" : var.sku_name
  redis_family = local.is_dev ? "C" : var.family
}

# =============================================================================
# Azure Cache for Redis
# =============================================================================

resource "azurerm_redis_cache" "main" {
  name                = "${var.project_name}-${var.environment}-redis"
  location            = var.location
  resource_group_name = var.resource_group_name
  capacity            = local.redis_capacity
  family              = local.redis_family
  sku_name            = local.redis_sku

  # TLS required (mirrors AWS transit encryption)
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  # VNet integration (Premium only)
  subnet_id = local.redis_sku == "Premium" ? var.subnet_id : null

  # Redis configuration
  redis_configuration {
    maxmemory_reserved            = local.is_dev ? 2 : 10
    maxmemory_delta               = local.is_dev ? 2 : 10
    maxmemory_policy              = "allkeys-lru"
    rdb_backup_enabled            = !local.is_dev
    rdb_backup_frequency          = local.is_dev ? null : 60
    rdb_backup_max_snapshot_count = local.is_dev ? null : 1
  }

  # Clustering (Premium only)
  shard_count = local.redis_sku == "Premium" ? (local.is_production ? 2 : 1) : null

  # Availability zones (Premium only)
  zones = local.redis_sku == "Premium" ? ["1", "2"] : null

  # Patching schedule
  patch_schedule {
    day_of_week    = "Sunday"
    start_hour_utc = 6
  }

  tags = var.tags
}

# =============================================================================
# Store credentials in Key Vault
# =============================================================================

resource "azurerm_key_vault_secret" "redis_primary_key" {
  name         = "redis-primary-key"
  value        = azurerm_redis_cache.main.primary_access_key
  key_vault_id = var.key_vault_id

  tags = var.tags
}

resource "azurerm_key_vault_secret" "redis_connection_string" {
  name         = "redis-connection-string"
  value        = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}"
  key_vault_id = var.key_vault_id

  tags = var.tags
}
