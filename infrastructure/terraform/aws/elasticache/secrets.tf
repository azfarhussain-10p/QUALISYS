# Secrets Manager Configuration
# Story: 0-5 Redis Caching Layer
# AC: 7 - Redis connection string stored in AWS Secrets Manager
# Tasks 5.1-5.3

# =============================================================================
# Auth Token Generation
# =============================================================================

resource "random_password" "redis_auth" {
  length  = 64
  special = false
  # ElastiCache auth tokens: 16-128 chars, printable ASCII excluding @, ", /
  # Using alphanumeric only for maximum compatibility with connection URIs
}

# =============================================================================
# Redis Connection Secret (AC7)
# Task 5.1 - Create secret: qualisys/redis/connection
# Task 5.2 - Store connection info: primary endpoint, reader endpoint, port, auth token
# =============================================================================

resource "aws_secretsmanager_secret" "redis_connection" {
  name        = "${var.project_name}/redis/connection"
  description = "ElastiCache Redis connection credentials"

  kms_key_id = aws_kms_key.elasticache.arn

  tags = {
    Name = "${var.project_name}-redis-connection-secret"
  }
}

resource "aws_secretsmanager_secret_version" "redis_connection" {
  secret_id = aws_secretsmanager_secret.redis_connection.id

  secret_string = jsonencode({
    engine = "redis"
    # Cluster mode enabled: configuration endpoint handles automatic slot discovery
    # Both primary and reader traffic routed through cluster protocol
    primary_endpoint = aws_elasticache_replication_group.redis.configuration_endpoint_address
    reader_endpoint  = aws_elasticache_replication_group.redis.configuration_endpoint_address
    port             = 6379
    auth_token       = random_password.redis_auth.result
    ssl_enabled      = true
    # Connection URI (rediss:// = Redis over TLS)
    connection_uri = "rediss://:${random_password.redis_auth.result}@${aws_elasticache_replication_group.redis.configuration_endpoint_address}:6379"
  })
}

# =============================================================================
# IAM Policy for K8s Pods to Read Redis Secret (Task 5.3)
# This policy is used by IRSA (IAM Roles for Service Accounts) to allow
# application pods to retrieve Redis credentials from Secrets Manager.
# =============================================================================

resource "aws_iam_policy" "redis_secret_read" {
  name        = "${var.project_name}-redis-secret-read"
  description = "Allow K8s pods to read Redis connection secret via IRSA"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = aws_secretsmanager_secret.redis_connection.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
        ]
        Resource = aws_kms_key.elasticache.arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}
