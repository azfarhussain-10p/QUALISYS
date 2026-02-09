output "vnet_id" {
  description = "ID of the Virtual Network"
  value       = azurerm_virtual_network.main.id
}

output "vnet_name" {
  description = "Name of the Virtual Network"
  value       = azurerm_virtual_network.main.name
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = azurerm_subnet.public.id
}

output "aks_subnet_id" {
  description = "ID of the AKS subnet"
  value       = azurerm_subnet.aks.id
}

output "postgresql_subnet_id" {
  description = "ID of the PostgreSQL subnet"
  value       = azurerm_subnet.postgresql.id
}

output "redis_subnet_id" {
  description = "ID of the Redis subnet"
  value       = azurerm_subnet.redis.id
}

output "appgw_subnet_id" {
  description = "ID of the Application Gateway subnet"
  value       = azurerm_subnet.appgw.id
}

output "nat_gateway_public_ip" {
  description = "Public IP of the NAT Gateway"
  value       = azurerm_public_ip.nat.ip_address
}

output "postgresql_private_dns_zone_id" {
  description = "ID of the PostgreSQL private DNS zone"
  value       = azurerm_private_dns_zone.postgresql.id
}
