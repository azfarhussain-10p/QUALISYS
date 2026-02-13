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
# LLM API Keys (Story 0-7 AC5 / Story 0-22 AC1, AC2, AC8, AC9, AC10)
# Placeholder secrets — actual API keys set manually after terraform apply.
# lifecycle.ignore_changes prevents Terraform from overwriting manual updates.
# =============================================================================

resource "aws_secretsmanager_secret" "llm_openai" {
  name        = "${var.project_name}/llm/openai"
  description = "OpenAI API key for LangChain AI agents (Epic 2)"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name             = "${var.project_name}-llm-openai"
    Category         = "llm"
    Epic             = "2"
    RotationSchedule = "quarterly"
    NextRotation     = "2026-07-01"
    BillingAlert     = "200-usd-hard-limit"
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
  description = "Anthropic API key for Claude AI agents (Epic 2)"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name             = "${var.project_name}-llm-anthropic"
    Category         = "llm"
    Epic             = "2"
    RotationSchedule = "quarterly"
    NextRotation     = "2026-07-01"
    BillingAlert     = "200-usd-budget"
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
# OAuth Credentials (Story 0-7 AC6 / Story 0-22 AC3, AC8)
# =============================================================================

resource "aws_secretsmanager_secret" "oauth_google" {
  name        = "${var.project_name}/oauth/google"
  description = "Google OAuth 2.0 client credentials for SSO (Epic 1)"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name             = "${var.project_name}-oauth-google"
    Category         = "oauth"
    Epic             = "1"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
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
# Email Service API Key (Story 0-7 AC7 / Story 0-22 AC4, AC8)
# =============================================================================

resource "aws_secretsmanager_secret" "email_sendgrid" {
  name        = "${var.project_name}/email/sendgrid"
  description = "SendGrid API key for transactional emails (Epic 1)"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name             = "${var.project_name}-email-sendgrid"
    Category         = "email"
    Epic             = "1"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
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

# =============================================================================
# GitHub App Credentials (Story 0-22 AC7, AC8)
# =============================================================================

resource "aws_secretsmanager_secret" "github_app" {
  name        = "${var.project_name}/integrations/github-app"
  description = "GitHub App credentials for repository integration (Epic 3)"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name             = "${var.project_name}-github-app"
    Category         = "integrations"
    Epic             = "3"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
  }
}

resource "aws_secretsmanager_secret_version" "github_app" {
  secret_id = aws_secretsmanager_secret.github_app.id

  secret_string = jsonencode({
    app_id         = "REPLACE_WITH_GITHUB_APP_ID"
    client_id      = "REPLACE_WITH_GITHUB_CLIENT_ID"
    client_secret  = "REPLACE_WITH_GITHUB_CLIENT_SECRET"
    private_key    = "REPLACE_WITH_GITHUB_PRIVATE_KEY_PEM"
    webhook_secret = "REPLACE_WITH_GITHUB_WEBHOOK_SECRET"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# Jira API Token (Story 0-22 AC5, AC8 — can defer to Epic 5)
# =============================================================================

resource "aws_secretsmanager_secret" "jira_api_token" {
  name        = "${var.project_name}/integrations/jira"
  description = "Jira API token for issue tracking integration (Epic 5)"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name             = "${var.project_name}-jira-api-token"
    Category         = "integrations"
    Epic             = "5"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
    Status           = "pending-provisioning"
  }
}

resource "aws_secretsmanager_secret_version" "jira_api_token" {
  secret_id = aws_secretsmanager_secret.jira_api_token.id

  secret_string = jsonencode({
    email     = "REPLACE_WITH_JIRA_SERVICE_ACCOUNT_EMAIL"
    api_token = "REPLACE_WITH_JIRA_API_TOKEN"
    base_url  = "REPLACE_WITH_JIRA_BASE_URL"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# Slack Webhook URL (Story 0-22 AC6, AC8 — can defer to Epic 5)
# =============================================================================

resource "aws_secretsmanager_secret" "slack_webhook" {
  name        = "${var.project_name}/integrations/slack-webhook"
  description = "Slack webhook URL for notifications (Epic 5)"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name             = "${var.project_name}-slack-webhook"
    Category         = "integrations"
    Epic             = "5"
    RotationSchedule = "on-compromise"
  }
}

resource "aws_secretsmanager_secret_version" "slack_webhook" {
  secret_id = aws_secretsmanager_secret.slack_webhook.id

  secret_string = jsonencode({
    webhook_url = "REPLACE_WITH_SLACK_WEBHOOK_URL"
    channel     = "#qualisys-alerts"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
