# Secrets Manager Secrets
# Story: 0-7 Secret Management
# AC: 1 - AWS Secrets Manager configured as primary secret store
# AC: 2 - Database connection string (already exists in rds/secrets.tf)
# AC: 3 - Redis connection string (already exists in elasticache/secrets.tf)
# AC: 4 - JWT signing secret (256-bit random)
# AC: 5 - LLM API keys (OpenAI, Anthropic)
# AC: 6 - OAuth credentials (Google)
# AC: 7 - Email service API key (SendGrid)

# =============================================================================
# KMS Key for Secret Encryption (Task 1.2)
# Dedicated KMS key for application secrets created by this module.
# Database and Redis secrets use their own KMS keys (Stories 0.4, 0.5).
# =============================================================================

resource "aws_kms_key" "secrets" {
  description             = "KMS key for application secrets encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-secrets-encryption-key"
  }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.project_name}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# =============================================================================
# AC2 & AC3 - Database and Redis Connection Secrets
# These secrets already exist from Stories 0.4 and 0.5:
#   - qualisys/database/connection → rds/secrets.tf (aws_secretsmanager_secret.db_connection)
#   - qualisys/database/master → rds/secrets.tf (aws_secretsmanager_secret.db_master)
#   - qualisys/redis/connection → elasticache/secrets.tf (aws_secretsmanager_secret.redis_connection)
# No new resources needed — cross-referenced in outputs.
# =============================================================================

# =============================================================================
# JWT Signing Secret (AC4 - Tasks 2.3, 2.4)
# 256-bit (32 bytes) cryptographically random secret for JWT signing.
# =============================================================================

resource "random_password" "jwt_signing_key" {
  length  = 64
  special = false
  # 64 alphanumeric characters (a-z, A-Z, 0-9) = ~381 bits entropy, exceeds 256-bit requirement
}

resource "aws_secretsmanager_secret" "jwt_signing_key" {
  name        = "${var.project_name}/jwt/signing-key"
  description = "JWT signing secret (256-bit) for authentication token signing"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name     = "${var.project_name}-jwt-signing-key"
    Category = "jwt"
  }
}

resource "aws_secretsmanager_secret_version" "jwt_signing_key" {
  secret_id = aws_secretsmanager_secret.jwt_signing_key.id

  secret_string = jsonencode({
    secret = random_password.jwt_signing_key.result
  })
}

# =============================================================================
# LLM API Keys (AC5 - Tasks 3.1, 3.2)
# Placeholder secrets — actual API keys set manually after terraform apply.
# lifecycle.ignore_changes prevents Terraform from overwriting manual updates.
# =============================================================================

resource "aws_secretsmanager_secret" "llm_openai" {
  name        = "${var.project_name}/llm/openai"
  description = "OpenAI API key for AI agent operations"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name     = "${var.project_name}-llm-openai"
    Category = "llm"
  }
}

resource "aws_secretsmanager_secret_version" "llm_openai" {
  secret_id = aws_secretsmanager_secret.llm_openai.id

  secret_string = jsonencode({
    api_key = "REPLACE_WITH_ACTUAL_OPENAI_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "llm_anthropic" {
  name        = "${var.project_name}/llm/anthropic"
  description = "Anthropic API key for AI agent operations"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name     = "${var.project_name}-llm-anthropic"
    Category = "llm"
  }
}

resource "aws_secretsmanager_secret_version" "llm_anthropic" {
  secret_id = aws_secretsmanager_secret.llm_anthropic.id

  secret_string = jsonencode({
    api_key = "REPLACE_WITH_ACTUAL_ANTHROPIC_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# OAuth Credentials (AC6 - Task 3.3)
# =============================================================================

resource "aws_secretsmanager_secret" "oauth_google" {
  name        = "${var.project_name}/oauth/google"
  description = "Google OAuth 2.0 client credentials for SSO"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name     = "${var.project_name}-oauth-google"
    Category = "oauth"
  }
}

resource "aws_secretsmanager_secret_version" "oauth_google" {
  secret_id = aws_secretsmanager_secret.oauth_google.id

  secret_string = jsonencode({
    client_id     = "REPLACE_WITH_GOOGLE_CLIENT_ID"
    client_secret = "REPLACE_WITH_GOOGLE_CLIENT_SECRET"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# Email Service API Key (AC7 - Task 3.4)
# =============================================================================

resource "aws_secretsmanager_secret" "email_sendgrid" {
  name        = "${var.project_name}/email/sendgrid"
  description = "SendGrid API key for transactional email delivery"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name     = "${var.project_name}-email-sendgrid"
    Category = "email"
  }
}

resource "aws_secretsmanager_secret_version" "email_sendgrid" {
  secret_id = aws_secretsmanager_secret.email_sendgrid.id

  secret_string = jsonencode({
    api_key = "REPLACE_WITH_SENDGRID_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
