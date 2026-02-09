# IAM Policy Documents
# Story: 0-1 Cloud Account & IAM Setup
# AC: 2 - Appropriate policies for each role
# AC: 3 - Least-privilege service account policies
# AC: 5 - All policies documented with justification

# =============================================================================
# Developer Policy (AC2)
# Justification: Developers need EKS access for debugging, ECR pull for local
# testing, S3 read for artifacts, and CloudWatch for log analysis.
# =============================================================================
resource "aws_iam_policy" "developer" {
  name        = "QualisysDeveloperPolicy"
  description = "Developer access: EKS describe, ECR pull, S3 read, CloudWatch logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EKSReadAccess"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters",
          "eks:ListNodegroups",
          "eks:DescribeNodegroup",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      },
      {
        Sid    = "ECRPullAccess"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:DescribeRepositories",
          "ecr:ListImages"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ReadAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:GetLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:FilterLogEvents",
          "logs:StartQuery",
          "logs:GetQueryResults"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# CI/CD Policy (AC2)
# Justification: CI/CD pipeline needs ECR push for images, EKS deploy to staging
# namespace ONLY. CANNOT read secrets, CANNOT exec into pods (Red Team constraint).
# =============================================================================
resource "aws_iam_policy" "cicd" {
  name        = "QualisysCICDPolicy"
  description = "CI/CD: ECR push, EKS staging-only deploy. NO secrets read, NO pod exec"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRAuthToken"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Sid    = "ECRPushPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeRepositories",
          "ecr:ListImages"
        ]
        Resource = "arn:aws:ecr:*:*:repository/qualisys-*"
      },
      {
        Sid    = "EKSStagingDeploy"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ArtifactAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::qualisys-ci-artifacts",
          "arn:aws:s3:::qualisys-ci-artifacts/*"
        ]
      },
      {
        Sid    = "DenySecretsAccess"
        Effect = "Deny"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# RDS Service Policy (AC3)
# Justification: RDS service account needs limited access for database
# management. NO superuser privileges enforced at PostgreSQL level.
# =============================================================================
resource "aws_iam_policy" "rds_service" {
  name        = "QualisysRDSServicePolicy"
  description = "RDS service: database management, backup, monitoring. NO superuser."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RDSManagement"
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          "rds:CreateDBSnapshot",
          "rds:DescribeDBSnapshots",
          "rds:ModifyDBInstance",
          "rds:RebootDBInstance"
        ]
        Resource = "arn:aws:rds:*:*:db:qualisys-*"
      },
      {
        Sid    = "RDSMonitoring"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics",
          "logs:GetLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# ElastiCache Service Policy (AC3)
# Justification: ElastiCache service needs cluster management access for Redis
# provisioning, replication group management, and monitoring.
# =============================================================================
resource "aws_iam_policy" "elasticache_service" {
  name        = "QualisysElastiCacheServicePolicy"
  description = "ElastiCache service: cluster management and monitoring"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ElastiCacheManagement"
        Effect = "Allow"
        Action = [
          "elasticache:DescribeCacheClusters",
          "elasticache:DescribeReplicationGroups",
          "elasticache:ModifyCacheCluster",
          "elasticache:ModifyReplicationGroup",
          "elasticache:ListTagsForResource"
        ]
        Resource = [
          "arn:aws:elasticache:*:*:cluster:qualisys-*",
          "arn:aws:elasticache:*:*:replicationgroup:qualisys-*"
        ]
      },
      {
        Sid    = "ElastiCacheMonitoring"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# ECR Service Policy (AC3)
# Justification: ECR service account for image management, vulnerability
# scanning, and lifecycle policy enforcement.
# =============================================================================
resource "aws_iam_policy" "ecr_service" {
  name        = "QualisysECRServicePolicy"
  description = "ECR service: image push/pull, scanning, lifecycle management"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRImageManagement"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages",
          "ecr:DescribeImageScanFindings"
        ]
        Resource = "arn:aws:ecr:*:*:repository/qualisys-*"
      },
      {
        Sid    = "ECRAuthToken"
        Effect = "Allow"
        Action = "ecr:GetAuthorizationToken"
        Resource = "*"
      }
    ]
  })
}
