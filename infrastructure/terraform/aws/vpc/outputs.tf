# VPC Outputs
# Story: 0-2 VPC & Network Configuration
# These outputs are consumed by downstream stories:
#   - Story 0.3 (Kubernetes): vpc_id, private_subnet_ids, k8s_nodes_security_group_id
#   - Story 0.4 (PostgreSQL): database_subnet_ids, rds_security_group_id, db_subnet_group_name
#   - Story 0.5 (Redis): database_subnet_ids, elasticache_security_group_id, elasticache_subnet_group_name
#   - Story 0.13 (Load Balancer): public_subnet_ids, alb_security_group_id

# =============================================================================
# VPC
# =============================================================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

# =============================================================================
# Subnet IDs
# =============================================================================

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "database_subnet_ids" {
  description = "IDs of the database subnets"
  value       = aws_subnet.database[*].id
}

# =============================================================================
# Subnet Groups
# =============================================================================

output "db_subnet_group_name" {
  description = "Name of the RDS DB subnet group"
  value       = aws_db_subnet_group.database.name
}

output "elasticache_subnet_group_name" {
  description = "Name of the ElastiCache subnet group"
  value       = aws_elasticache_subnet_group.database.name
}

# =============================================================================
# Security Group IDs
# =============================================================================

output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = aws_security_group.alb.id
}

output "k8s_nodes_security_group_id" {
  description = "ID of the Kubernetes nodes security group"
  value       = aws_security_group.k8s_nodes.id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds.id
}

output "elasticache_security_group_id" {
  description = "ID of the ElastiCache security group"
  value       = aws_security_group.elasticache.id
}

# =============================================================================
# NAT Gateway IPs (useful for allowlisting)
# =============================================================================

output "nat_gateway_public_ips" {
  description = "Public IPs of the NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}

# =============================================================================
# Flow Logs
# =============================================================================

output "flow_log_group_name" {
  description = "CloudWatch Log Group name for VPC Flow Logs"
  value       = aws_cloudwatch_log_group.vpc_flow_logs.name
}
