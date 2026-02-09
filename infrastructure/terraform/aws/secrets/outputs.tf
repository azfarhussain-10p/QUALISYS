# Secrets Manager Outputs
# Story: 0-7 Secret Management
# These outputs are consumed by downstream stories:
#   - Epic 1 (Foundation): All secret ARNs for application pods
#   - Epic 2 (AI Agent Platform): LLM API key secret ARNs
#   - All Epics: ExternalSecrets IRSA role ARN, IAM policy ARNs

# =============================================================================
# Secret ARNs — Infrastructure (database, redis from Stories 0.4, 0.5)
# =============================================================================

output "database_secret_arn" {
  description = "ARN of the database connection secret (from Story 0.4)"
  value       = aws_secretsmanager_secret.db_connection.arn
}

output "redis_secret_arn" {
  description = "ARN of the Redis connection secret (from Story 0.5)"
  value       = aws_secretsmanager_secret.redis_connection.arn
}

output "jwt_secret_arn" {
  description = "ARN of the JWT signing key secret"
  value       = aws_secretsmanager_secret.jwt_signing_key.arn
}

# =============================================================================
# Secret ARNs — Third-Party Services
# =============================================================================

output "openai_secret_arn" {
  description = "ARN of the OpenAI API key secret"
  value       = aws_secretsmanager_secret.llm_openai.arn
}

output "anthropic_secret_arn" {
  description = "ARN of the Anthropic API key secret"
  value       = aws_secretsmanager_secret.llm_anthropic.arn
}

output "oauth_google_secret_arn" {
  description = "ARN of the Google OAuth credentials secret"
  value       = aws_secretsmanager_secret.oauth_google.arn
}

output "email_sendgrid_secret_arn" {
  description = "ARN of the SendGrid email API key secret"
  value       = aws_secretsmanager_secret.email_sendgrid.arn
}

# =============================================================================
# KMS
# =============================================================================

output "secrets_kms_key_arn" {
  description = "ARN of the KMS key used for application secrets encryption"
  value       = aws_kms_key.secrets.arn
}

# =============================================================================
# IAM Policies — Category-Based Access
# =============================================================================

output "secrets_read_infra_policy_arn" {
  description = "ARN of IAM policy for reading infrastructure secrets (DB, Redis, JWT)"
  value       = aws_iam_policy.secrets_read_infra.arn
}

output "secrets_read_llm_policy_arn" {
  description = "ARN of IAM policy for reading LLM API key secrets"
  value       = aws_iam_policy.secrets_read_llm.arn
}

output "secrets_read_integrations_policy_arn" {
  description = "ARN of IAM policy for reading integration secrets (OAuth, email)"
  value       = aws_iam_policy.secrets_read_integrations.arn
}

# =============================================================================
# ExternalSecrets Operator
# =============================================================================

output "external_secrets_role_arn" {
  description = "ARN of the IRSA role for ExternalSecrets Operator"
  value       = aws_iam_role.external_secrets.arn
}

output "external_secrets_policy_arn" {
  description = "ARN of the IAM policy for ExternalSecrets Operator"
  value       = aws_iam_policy.external_secrets.arn
}

# =============================================================================
# Rotation
# =============================================================================

output "db_rotation_lambda_arn" {
  description = "ARN of the database password rotation Lambda function"
  value       = aws_serverlessapplicationrepository_cloudformation_stack.db_rotation.outputs["RotationLambdaARN"]
}

output "secrets_alerts_topic_arn" {
  description = "ARN of the SNS topic for secret rotation and unauthorized access alerts"
  value       = aws_sns_topic.secrets_alerts.arn
}
