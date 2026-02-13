# DNS Outputs - Azure DNS
# Story: 0-13 Load Balancer & Ingress Configuration

output "production_zone_name_servers" {
  description = "Name servers for qualisys.io (configure at domain registrar)"
  value       = azurerm_dns_zone.qualisys_io.name_servers
}

output "staging_zone_name_servers" {
  description = "Name servers for qualisys.dev (configure at domain registrar)"
  value       = azurerm_dns_zone.qualisys_dev.name_servers
}

output "app_domain" {
  description = "Production web application URL"
  value       = "https://app.${azurerm_dns_zone.qualisys_io.name}"
}

output "api_domain" {
  description = "Production API URL"
  value       = "https://api.${azurerm_dns_zone.qualisys_io.name}"
}

output "staging_domain" {
  description = "Staging URL"
  value       = "https://staging.${azurerm_dns_zone.qualisys_dev.name}"
}
