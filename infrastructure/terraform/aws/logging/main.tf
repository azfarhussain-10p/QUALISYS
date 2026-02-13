# CloudWatch Log Groups for QUALISYS
# Story: 0-20 Log Aggregation (ELK or CloudWatch)
# AC: 1 - Log aggregation system deployed (CloudWatch Logs)
# AC: 7 - Log retention: 30 days staging, 90 days production

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# KMS Key for CloudWatch Logs encryption (Task 1.6)
# -----------------------------------------------------------------------------
resource "aws_kms_key" "logs" {
  description             = "KMS key for QUALISYS CloudWatch Logs encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableIAMUserPermissions"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowCloudWatchLogs"
        Effect    = "Allow"
        Principal = { Service = "logs.${data.aws_region.current.name}.amazonaws.com" }
        Action    = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*", "kms:DescribeKey"]
        Resource  = "*"
      }
    ]
  })

  tags = {
    Name    = "qualisys-logs-kms"
    Project = "qualisys"
  }
}

resource "aws_kms_alias" "logs" {
  name          = "alias/qualisys-logs"
  target_key_id = aws_kms_key.logs.key_id
}

# -----------------------------------------------------------------------------
# Staging Log Groups (Task 1.1, 1.2) — 30 day retention (AC7)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "api_staging" {
  name              = "/qualisys/staging/api"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.logs.arn

  tags = {
    Environment = "staging"
    Service     = "api"
    Project     = "qualisys"
  }
}

resource "aws_cloudwatch_log_group" "worker_staging" {
  name              = "/qualisys/staging/worker"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.logs.arn

  tags = {
    Environment = "staging"
    Service     = "worker"
    Project     = "qualisys"
  }
}

# -----------------------------------------------------------------------------
# Production Log Groups (Task 1.3, 1.4) — 90 day retention (AC7)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "api_production" {
  name              = "/qualisys/production/api"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn

  tags = {
    Environment = "production"
    Service     = "api"
    Project     = "qualisys"
  }
}

resource "aws_cloudwatch_log_group" "worker_production" {
  name              = "/qualisys/production/worker"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn

  tags = {
    Environment = "production"
    Service     = "worker"
    Project     = "qualisys"
  }
}

# -----------------------------------------------------------------------------
# Kubernetes System Log Group (AC4)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "kubernetes" {
  name              = "/qualisys/kubernetes/system"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.logs.arn

  tags = {
    Environment = "shared"
    Service     = "kubernetes"
    Project     = "qualisys"
  }
}

# -----------------------------------------------------------------------------
# IRSA Role for Fluent Bit (Task 2.4)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "fluent_bit" {
  name = "qualisys-fluent-bit"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.eks_oidc_provider}:sub" = "system:serviceaccount:monitoring:fluent-bit"
            "${var.eks_oidc_provider}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name    = "qualisys-fluent-bit"
    Project = "qualisys"
  }
}

resource "aws_iam_role_policy" "fluent_bit_cloudwatch" {
  name = "fluent-bit-cloudwatch"
  role = aws_iam_role.fluent_bit.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/qualisys/*"
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# IAM Policy for log access (Task 6.1)
# -----------------------------------------------------------------------------
resource "aws_iam_policy" "log_reader" {
  name        = "qualisys-log-reader"
  description = "Read access to QUALISYS CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
          "logs:GetLogRecord",
          "logs:GetQueryResults",
          "logs:StartQuery",
          "logs:StopQuery",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/qualisys/*"
        ]
      }
    ]
  })

  tags = {
    Name    = "qualisys-log-reader"
    Project = "qualisys"
  }
}
