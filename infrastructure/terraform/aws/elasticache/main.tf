# ElastiCache Redis Cluster
# Story: 0-5 Redis Caching Layer
# AC: 1 - Redis 7+ cluster created
# AC: 2 - Node type per environment
# AC: 3 - Cluster mode with 2 shards
# AC: 4 - Multi-AZ with automatic failover
# AC: 5 - Encryption in transit (TLS)
# AC: 6 - Encryption at rest

# =============================================================================
# Locals — Environment-Dependent Configuration
# =============================================================================

locals {
  is_production = var.environment == "production"
  is_dev        = var.environment == "dev"

  # AC2: cache.t3.micro (dev), cache.t3.small (staging), cache.r5.large (production)
  redis_node_type = (
    var.redis_node_type_override != ""
    ? var.redis_node_type_override
    : (local.is_production ? "cache.r5.large" : (local.is_dev ? "cache.t3.micro" : "cache.t3.small"))
  )

  # AC3: 1 shard for dev, 2 shards for staging/production
  redis_num_shards = local.is_dev ? 1 : 2

  # Replicas: 0 for dev (cost savings), 1 for staging/production (HA)
  redis_replicas_per_shard = local.is_dev ? 0 : 1

  # AC4: Multi-AZ and automatic failover require at least 1 replica
  redis_multi_az           = !local.is_dev
  redis_automatic_failover = !local.is_dev
}

# =============================================================================
# KMS Key for ElastiCache Encryption at Rest (AC6)
# =============================================================================

resource "aws_kms_key" "elasticache" {
  description             = "KMS key for ElastiCache Redis encryption at rest"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-elasticache-encryption-key"
  }
}

resource "aws_kms_alias" "elasticache" {
  name          = "alias/${var.project_name}-elasticache"
  target_key_id = aws_kms_key.elasticache.key_id
}

# =============================================================================
# Redis Replication Group (Tasks 4.1-4.10)
# =============================================================================

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.project_name}-redis"
  description          = "QUALISYS Redis cluster for caching, sessions, and rate limiting"

  # Task 4.2 - Redis 7.0+ (AC1)
  engine         = "redis"
  engine_version = var.redis_engine_version

  # Task 4.3 - Node type per environment (AC2)
  node_type = local.redis_node_type

  # Task 4.4 - Cluster mode with shards (AC3)
  num_node_groups         = local.redis_num_shards
  replicas_per_node_group = local.redis_replicas_per_shard

  # Task 4.6 - Multi-AZ and automatic failover (AC4)
  automatic_failover_enabled = local.redis_automatic_failover
  multi_az_enabled           = local.redis_multi_az

  # Task 4.7 - Encryption at rest (AC6)
  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.elasticache.arn

  # Task 4.8 - Encryption in transit / TLS (AC5)
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result

  # Task 4.9 - Associate custom parameter group (AC9)
  parameter_group_name = aws_elasticache_parameter_group.redis7.name

  # Task 4.10 - Associate subnet group from Story 0.2 (AC8)
  subnet_group_name = aws_elasticache_subnet_group.database.name

  # Security group from Story 0.2 (AC8)
  security_group_ids = [aws_security_group.elasticache.id]

  # Maintenance and snapshots
  maintenance_window      = var.redis_maintenance_window
  snapshot_window          = var.redis_snapshot_window
  snapshot_retention_limit = var.redis_snapshot_retention_days

  # Port
  port = 6379

  # Auto minor version upgrade
  auto_minor_version_upgrade = true

  # Apply changes immediately in dev, during maintenance window otherwise
  apply_immediately = local.is_dev

  tags = {
    Name = "${var.project_name}-redis"
  }
}
