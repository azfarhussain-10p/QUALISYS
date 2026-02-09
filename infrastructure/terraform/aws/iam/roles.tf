# IAM Role Definitions
# Story: 0-1 Cloud Account & IAM Setup
# AC: 2 - IAM roles: DevOps (admin), Developer (deploy), CI/CD (staging only)
# AC: 3 - Service accounts for EKS, RDS, ElastiCache, ECR

locals {
  account_id = data.aws_caller_identity.current.account_id
}

# =============================================================================
# Human User Roles (AC2)
# =============================================================================

# QualisysDevOpsAdmin - Admin access (PowerUserAccess + IAMFullAccess)
resource "aws_iam_role" "devops_admin" {
  name               = "QualisysDevOpsAdmin"
  description        = "DevOps admin role with full infrastructure management access"
  max_session_duration = 28800 # 8 hours

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          Bool = {
            "aws:MultiFactorAuthPresent" = "true"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "devops_power_user" {
  role       = aws_iam_role.devops_admin.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy_attachment" "devops_iam_full" {
  role       = aws_iam_role.devops_admin.name
  policy_arn = "arn:aws:iam::aws:policy/IAMFullAccess"
}

# QualisysDeveloper - Deploy permissions (limited)
resource "aws_iam_role" "developer" {
  name               = "QualisysDeveloper"
  description        = "Developer role with deploy permissions: EKS, ECR pull, S3 read, CloudWatch logs"
  max_session_duration = 28800

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          Bool = {
            "aws:MultiFactorAuthPresent" = "true"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "developer_policy" {
  role       = aws_iam_role.developer.name
  policy_arn = aws_iam_policy.developer.arn
}

# QualisysCICD - Staging-only deploy (AC2: no secrets read, no pod exec)
resource "aws_iam_role" "cicd" {
  name               = "QualisysCICD"
  description        = "CI/CD role: staging-only deploy, ECR push, no secrets read, no pod exec"
  max_session_duration = 3600 # 1 hour max for CI/CD sessions

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "codebuild.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cicd_policy" {
  role       = aws_iam_role.cicd.name
  policy_arn = aws_iam_policy.cicd.arn
}

# =============================================================================
# Service Account Roles (AC3)
# =============================================================================

# NOTE: EKS Cluster IAM role moved to eks/iam.tf (Story 0.3) as
# aws_iam_role.eks_service with associated policy attachments.
# Keeps EKS-specific IAM co-located with EKS Terraform resources.

# RDS Administration Service Account
# CRITICAL: NO SUPERUSER, NO BYPASSRLS (Red Team finding)
resource "aws_iam_role" "rds_service" {
  name        = "QualisysRDSService"
  description = "Service account for RDS administration - NO superuser privileges"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_service_policy" {
  role       = aws_iam_role.rds_service.name
  policy_arn = aws_iam_policy.rds_service.arn
}

# ElastiCache Management Service Account
resource "aws_iam_role" "elasticache_service" {
  name        = "QualisysElastiCacheService"
  description = "Service account for ElastiCache management"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "elasticache.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "elasticache_service_policy" {
  role       = aws_iam_role.elasticache_service.name
  policy_arn = aws_iam_policy.elasticache_service.arn
}

# ECR Image Push/Pull Service Account
resource "aws_iam_role" "ecr_service" {
  name        = "QualisysECRService"
  description = "Service account for ECR image push/pull"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecr.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
      {
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.cicd.arn
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_service_policy" {
  role       = aws_iam_role.ecr_service.name
  policy_arn = aws_iam_policy.ecr_service.arn
}
