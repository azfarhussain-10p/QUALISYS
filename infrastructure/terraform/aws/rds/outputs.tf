# RDS Outputs
# Story: 0-4 PostgreSQL Multi-Tenant Database
# These outputs are consumed by downstream stories:
#   - Story 0.14 (Test Database): db_subnet_group_name, db_parameter_group_name
#   - Epic 1 (Foundation): db_endpoint, db_connection_secret_arn
#   - Story 0.7 (Secret Management): db_connection_secret_arn, db_kms_key_arn

# =============================================================================
# Instance
# =============================================================================

output "db_instance_id" {
  description = "Identifier of the RDS instance"
  value       = aws_db_instance.main.id
}

output "db_endpoint" {
  description = "Connection endpoint for the RDS instance"
  value       = aws_db_instance.main.endpoint
}

output "db_address" {
  description = "Hostname of the RDS instance (without port)"
  value       = aws_db_instance.main.address
}

output "db_port" {
  description = "Port of the RDS instance"
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Name of the initial database"
  value       = aws_db_instance.main.db_name
}

output "db_engine_version_actual" {
  description = "Actual engine version running on the RDS instance"
  value       = aws_db_instance.main.engine_version_actual
}

# =============================================================================
# Security & Encryption
# =============================================================================

output "db_kms_key_arn" {
  description = "ARN of the KMS key used for RDS encryption"
  value       = aws_kms_key.rds.arn
}

# =============================================================================
# Secrets Manager
# =============================================================================

output "db_master_secret_arn" {
  description = "ARN of the Secrets Manager secret containing master credentials"
  value       = aws_secretsmanager_secret.db_master.arn
  sensitive   = true
}

output "db_connection_secret_arn" {
  description = "ARN of the Secrets Manager secret containing app_user connection string"
  value       = aws_secretsmanager_secret.db_connection.arn
}

output "db_secret_read_policy_arn" {
  description = "ARN of the IAM policy allowing pods to read the connection secret"
  value       = aws_iam_policy.rds_secret_read.arn
}

# =============================================================================
# Configuration (for downstream reuse)
# =============================================================================

output "db_parameter_group_name" {
  description = "Name of the custom parameter group"
  value       = aws_db_parameter_group.postgres15.name
}

output "db_monitoring_role_arn" {
  description = "ARN of the Enhanced Monitoring IAM role"
  value       = aws_iam_role.rds_monitoring.arn
}
