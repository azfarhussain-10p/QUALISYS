# ElastiCache Outputs
# Story: 0-5 Redis Caching Layer
# These outputs are consumed by downstream stories:
#   - Epic 1 (Foundation): Session management
#   - Epic 2 (AI Agent Platform): LLM response caching
#   - All Epics: Rate limiting infrastructure

# =============================================================================
# Cluster
# =============================================================================

output "redis_replication_group_id" {
  description = "ID of the Redis replication group"
  value       = aws_elasticache_replication_group.redis.id
}

output "redis_configuration_endpoint" {
  description = "Configuration endpoint for the Redis cluster (cluster mode enabled)"
  value       = aws_elasticache_replication_group.redis.configuration_endpoint_address
}

output "redis_port" {
  description = "Redis port number"
  value       = 6379
}

output "redis_engine_version_actual" {
  description = "Actual Redis engine version running"
  value       = aws_elasticache_replication_group.redis.engine_version_actual
}

# =============================================================================
# Encryption
# =============================================================================

output "redis_kms_key_arn" {
  description = "ARN of the KMS key used for Redis encryption"
  value       = aws_kms_key.elasticache.arn
}

# =============================================================================
# Secrets
# =============================================================================

output "redis_connection_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Redis connection info"
  value       = aws_secretsmanager_secret.redis_connection.arn
}

output "redis_secret_read_policy_arn" {
  description = "ARN of the IAM policy for reading the Redis connection secret"
  value       = aws_iam_policy.redis_secret_read.arn
}

# =============================================================================
# Parameter Group
# =============================================================================

output "redis_parameter_group_name" {
  description = "Name of the Redis parameter group"
  value       = aws_elasticache_parameter_group.redis7.name
}
