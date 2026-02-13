# DNS Configuration - Azure DNS
# Story: 0-13 Load Balancer & Ingress Configuration
# AC: 2 - Ingress routes traffic: app.qualisys.io -> web, api.qualisys.io -> api
# AC: 3 - Staging domain configured: staging.qualisys.dev
#
# Prerequisites:
#   - NGINX Ingress Controller deployed (creates Azure Load Balancer)
#   - Domain names registered (qualisys.io, qualisys.dev)
#
# Verify:
#   az network dns zone list --resource-group <rg>
#   az network dns record-set a list --zone-name qualisys.io --resource-group <rg>
#   dig app.qualisys.io
#   dig api.qualisys.io
#   dig staging.qualisys.dev

# =====================================================
# Production Domain: qualisys.io
# =====================================================

resource "azurerm_dns_zone" "qualisys_io" {
  name                = "qualisys.io"
  resource_group_name = var.resource_group_name

  tags = {
    Project     = "qualisys"
    Environment = "production"
    ManagedBy   = "terraform"
    Story       = "0-13"
  }
}

# app.qualisys.io -> Web frontend (production)
resource "azurerm_dns_a_record" "app_production" {
  name                = "app"
  zone_name           = azurerm_dns_zone.qualisys_io.name
  resource_group_name = var.resource_group_name
  ttl                 = 300
  target_resource_id  = var.ingress_public_ip_id
}

# api.qualisys.io -> API backend (production)
resource "azurerm_dns_a_record" "api_production" {
  name                = "api"
  zone_name           = azurerm_dns_zone.qualisys_io.name
  resource_group_name = var.resource_group_name
  ttl                 = 300
  target_resource_id  = var.ingress_public_ip_id
}

# =====================================================
# Staging Domain: qualisys.dev
# =====================================================

resource "azurerm_dns_zone" "qualisys_dev" {
  name                = "qualisys.dev"
  resource_group_name = var.resource_group_name

  tags = {
    Project     = "qualisys"
    Environment = "staging"
    ManagedBy   = "terraform"
    Story       = "0-13"
  }
}

# staging.qualisys.dev -> Staging environment
resource "azurerm_dns_a_record" "staging" {
  name                = "staging"
  zone_name           = azurerm_dns_zone.qualisys_dev.name
  resource_group_name = var.resource_group_name
  ttl                 = 300
  target_resource_id  = var.ingress_public_ip_id
}
