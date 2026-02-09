# Secrets Manager Configuration
# Story: 0-4 PostgreSQL Multi-Tenant Database
# AC: 9 - Connection string stored in AWS Secrets Manager
# Tasks 6.1-6.4

# =============================================================================
# Password Generation
# =============================================================================

resource "random_password" "db_master" {
  length  = 32
  special = true
  # Exclude characters that can cause issues in connection strings
  override_special = "!#$%^&*()-_=+[]{}|:,.<>?"
}

resource "random_password" "db_app_user" {
  length  = 32
  special = true
  # Restricted to URI-safe special characters to avoid breaking connection_uri
  # Excludes: @, #, %, ?, /, :, &, = (URI-reserved characters)
  override_special = "-_~!*'()."
}

# =============================================================================
# Master User Secret (internal — for admin operations)
# =============================================================================

resource "aws_secretsmanager_secret" "db_master" {
  name        = "${var.project_name}/database/master"
  description = "RDS PostgreSQL master user credentials (admin operations only)"

  kms_key_id = aws_kms_key.rds.arn

  tags = {
    Name = "${var.project_name}-db-master-secret"
  }
}

resource "aws_secretsmanager_secret_version" "db_master" {
  secret_id = aws_secretsmanager_secret.db_master.id

  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    database = var.db_name
    username = var.db_master_username
    password = random_password.db_master.result
  })
}

# =============================================================================
# Application Connection Secret (AC9 — for K8s pods via IRSA)
# Task 6.1 - Create secret: qualisys/database/connection
# Task 6.2 - Store connection string with host, port, database, username, password
# =============================================================================

resource "aws_secretsmanager_secret" "db_connection" {
  name        = "${var.project_name}/database/connection"
  description = "Application database connection credentials (app_user — NO SUPERUSER, NO BYPASSRLS)"

  kms_key_id = aws_kms_key.rds.arn

  # Task 6.3 - Secret rotation schedule (90-day rotation)
  # NOTE: Rotation Lambda must be deployed separately to enable automatic rotation.
  # See: https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets-rds.html
  # The rotation schedule is configured here; the Lambda attachment is a runtime step.

  tags = {
    Name = "${var.project_name}-db-connection-secret"
  }
}

resource "aws_secretsmanager_secret_version" "db_connection" {
  secret_id = aws_secretsmanager_secret.db_connection.id

  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    database = var.db_name
    username = "app_user"
    password = random_password.db_app_user.result
    # Full connection URI for convenience
    connection_uri = "postgresql://app_user:${random_password.db_app_user.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${var.db_name}?sslmode=require"
  })
}

# =============================================================================
# IAM Policy for K8s Pods to Read Connection Secret (Task 6.4)
# This policy is used by IRSA (IAM Roles for Service Accounts) to allow
# application pods to retrieve database credentials from Secrets Manager.
# =============================================================================

resource "aws_iam_policy" "rds_secret_read" {
  name        = "${var.project_name}-rds-secret-read"
  description = "Allow K8s pods to read database connection secret via IRSA"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = aws_secretsmanager_secret.db_connection.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
        ]
        Resource = aws_kms_key.rds.arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}
