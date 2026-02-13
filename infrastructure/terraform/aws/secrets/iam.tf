# IAM Policies and IRSA Configuration
# Story: 0-7 Secret Management
# AC: 8,9 - ExternalSecrets Operator IRSA
# AC: 11 - Access audit logging (CloudTrail + CloudWatch alarm)
# AC: 12 - IAM policies restrict secret access to specific roles
# Tasks 4.4, 6.1-6.6

# =============================================================================
# Category-Based IAM Policies (Tasks 6.1-6.3, AC12)
# Least-privilege: separate policies per secret category so each service
# only accesses the secrets it needs.
# =============================================================================

# Task 6.1 - Infrastructure secrets: database, redis, jwt
resource "aws_iam_policy" "secrets_read_infra" {
  name        = "${var.project_name}-secrets-read-infra"
  description = "Read access to infrastructure secrets (database, redis, jwt)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadInfraSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = [
          aws_secretsmanager_secret.db_connection.arn,
          aws_secretsmanager_secret.redis_connection.arn,
          aws_secretsmanager_secret.jwt_signing_key.arn,
        ]
      },
      {
        Sid    = "DecryptInfraSecrets"
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = [
          aws_kms_key.rds.arn,
          aws_kms_key.elasticache.arn,
          aws_kms_key.secrets.arn,
        ]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

# Task 6.2 - LLM secrets: openai, anthropic
resource "aws_iam_policy" "secrets_read_llm" {
  name        = "${var.project_name}-secrets-read-llm"
  description = "Read access to LLM API key secrets (OpenAI, Anthropic)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadLLMSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = [
          aws_secretsmanager_secret.llm_openai.arn,
          aws_secretsmanager_secret.llm_anthropic.arn,
        ]
      },
      {
        Sid    = "DecryptLLMSecrets"
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = [aws_kms_key.secrets.arn]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

# Task 6.3 - Integration secrets: oauth, email, github, jira, slack
# Story 0-22: Added GitHub App, Jira, Slack to integrations policy
resource "aws_iam_policy" "secrets_read_integrations" {
  name        = "${var.project_name}-secrets-read-integrations"
  description = "Read access to integration secrets (OAuth, email, GitHub, Jira, Slack)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadIntegrationSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = [
          aws_secretsmanager_secret.oauth_google.arn,
          aws_secretsmanager_secret.email_sendgrid.arn,
          aws_secretsmanager_secret.github_app.arn,
          aws_secretsmanager_secret.jira_api_token.arn,
          aws_secretsmanager_secret.slack_webhook.arn,
        ]
      },
      {
        Sid    = "DecryptIntegrationSecrets"
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = [aws_kms_key.secrets.arn]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

# =============================================================================
# ExternalSecrets Operator IRSA Role (Tasks 4.4, AC8, AC9)
# IRSA (IAM Roles for Service Accounts) allows the ExternalSecrets Operator
# to assume an IAM role and read secrets from AWS Secrets Manager.
# =============================================================================

resource "aws_iam_role" "external_secrets" {
  name        = "${var.project_name}-external-secrets"
  description = "IRSA role for ExternalSecrets Operator to read AWS Secrets Manager"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:${var.external_secrets_namespace}:${var.external_secrets_service_account}"
            "${replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-external-secrets-role"
  }
}

# ExternalSecrets Operator needs read access to ALL qualisys/* secrets
# so it can sync them to Kubernetes.
resource "aws_iam_policy" "external_secrets" {
  name        = "${var.project_name}-external-secrets"
  description = "Allow ExternalSecrets Operator to read all qualisys/* secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListSecrets"
        Effect = "Allow"
        Action = ["secretsmanager:ListSecrets"]
        # ListSecrets does not support resource-level restrictions
        Resource = "*"
      },
      {
        Sid    = "ReadAllQualisysSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"
      },
      {
        Sid    = "DecryptSecrets"
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        # Allow decrypt for all KMS keys when called via Secrets Manager
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "external_secrets" {
  role       = aws_iam_role.external_secrets.name
  policy_arn = aws_iam_policy.external_secrets.arn
}

# =============================================================================
# Audit Logging — CloudWatch Alarm for Unauthorized Access (Tasks 6.5-6.6)
# AC11 - CloudTrail already logs secretsmanager:GetSecretValue events
#         (monitoring/cloudtrail.tf from Story 0.1).
# Task 6.6 - EventBridge rule detects AccessDenied on Secrets Manager,
#             triggers CloudWatch alarm via SNS.
# =============================================================================

resource "aws_cloudwatch_event_rule" "secrets_unauthorized_access" {
  name        = "${var.project_name}-secrets-unauthorized-access"
  description = "Detect unauthorized Secrets Manager access attempts (AccessDenied)"

  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventSource = ["secretsmanager.amazonaws.com"]
      eventName   = ["GetSecretValue", "DescribeSecret", "PutSecretValue"]
      errorCode   = ["AccessDeniedException", "UnauthorizedAccess"]
    }
  })

  tags = {
    Name = "${var.project_name}-secrets-unauthorized-access"
  }
}

resource "aws_cloudwatch_event_target" "secrets_unauthorized_access_sns" {
  rule      = aws_cloudwatch_event_rule.secrets_unauthorized_access.name
  target_id = "unauthorized-access-sns-alert"
  arn       = aws_sns_topic.secrets_alerts.arn
}

# CloudWatch alarm on the EventBridge rule invocations
resource "aws_cloudwatch_metric_alarm" "secrets_unauthorized_access" {
  alarm_name          = "${var.project_name}-secrets-unauthorized-access"
  alarm_description   = "Alarm when unauthorized Secrets Manager access is detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Invocations"
  namespace           = "AWS/Events"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.secrets_alerts.arn]

  dimensions = {
    RuleName = aws_cloudwatch_event_rule.secrets_unauthorized_access.name
  }

  tags = {
    Name = "${var.project_name}-secrets-unauthorized-access-alarm"
  }
}
