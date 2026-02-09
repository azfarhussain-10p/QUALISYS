# Azure Database for PostgreSQL Flexible Server
# QUALISYS Azure Infrastructure — mirrors AWS RDS PostgreSQL configuration
# PostgreSQL 15, zone-redundant HA, pgvector extension

locals {
  is_production = var.environment == "production"

  # SKU mapping: dev=B_Standard_B2s, staging=GP_Standard_D2s_v3, prod=GP_Standard_D4s_v3
  sku_name = (
    var.sku_name != ""
    ? var.sku_name
    : (local.is_production ? "GP_Standard_D4s_v3" : (var.environment == "staging" ? "GP_Standard_D2s_v3" : "B_Standard_B2s"))
  )
}

# =============================================================================
# Admin Password
# =============================================================================

resource "random_password" "postgresql_admin" {
  length  = 32
  special = true
}

# =============================================================================
# PostgreSQL Flexible Server
# =============================================================================

resource "azurerm_postgresql_flexible_server" "main" {
  name                = "${var.project_name}-${var.environment}-psql"
  resource_group_name = var.resource_group_name
  location            = var.location
  version             = var.postgresql_version
  sku_name            = local.sku_name

  administrator_login    = var.admin_username
  administrator_password = random_password.postgresql_admin.result

  storage_mb = var.storage_mb

  # Network — VNet integration via delegated subnet
  delegated_subnet_id = var.delegated_subnet_id
  private_dns_zone_id = var.private_dns_zone_id

  # High availability — zone redundant for production
  dynamic "high_availability" {
    for_each = local.is_production ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  # Backup
  backup_retention_days        = local.is_production ? 35 : 7
  geo_redundant_backup_enabled = local.is_production

  # Maintenance window
  maintenance_window {
    day_of_week  = 0
    start_hour   = 4
    start_minute = 0
  }

  tags = var.tags
}

# =============================================================================
# PostgreSQL Database
# =============================================================================

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = var.db_name
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "UTF8"
}

# =============================================================================
# Server Configuration — pgvector, connection limits
# =============================================================================

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR,PG_TRGM,PGCRYPTO,UUID-OSSP"
}

resource "azurerm_postgresql_flexible_server_configuration" "max_connections" {
  name      = "max_connections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = var.environment == "production" ? "200" : "100"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_checkpoints" {
  name      = "log_checkpoints"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_connections" {
  name      = "log_connections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

# =============================================================================
# Store credentials in Key Vault
# =============================================================================

resource "azurerm_key_vault_secret" "postgresql_admin_password" {
  name         = "postgresql-admin-password"
  value        = random_password.postgresql_admin.result
  key_vault_id = var.key_vault_id

  tags = var.tags
}

resource "azurerm_key_vault_secret" "postgresql_connection_string" {
  name         = "postgresql-connection-string"
  value        = "postgresql://${var.admin_username}:${random_password.postgresql_admin.result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.db_name}?sslmode=require"
  key_vault_id = var.key_vault_id

  tags = var.tags
}
