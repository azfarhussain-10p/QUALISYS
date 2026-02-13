# DNS Outputs - AWS Route 53
# Story: 0-13 Load Balancer & Ingress Configuration

output "production_zone_id" {
  description = "Route 53 hosted zone ID for qualisys.io"
  value       = aws_route53_zone.qualisys_io.zone_id
}

output "production_zone_name_servers" {
  description = "Name servers for qualisys.io (configure at domain registrar)"
  value       = aws_route53_zone.qualisys_io.name_servers
}

output "staging_zone_id" {
  description = "Route 53 hosted zone ID for qualisys.dev"
  value       = aws_route53_zone.qualisys_dev.zone_id
}

output "staging_zone_name_servers" {
  description = "Name servers for qualisys.dev (configure at domain registrar)"
  value       = aws_route53_zone.qualisys_dev.name_servers
}

output "app_domain" {
  description = "Production web application URL"
  value       = "https://${aws_route53_record.app_production.name}"
}

output "api_domain" {
  description = "Production API URL"
  value       = "https://${aws_route53_record.api_production.name}"
}

output "staging_domain" {
  description = "Staging URL"
  value       = "https://${aws_route53_record.staging.name}"
}
