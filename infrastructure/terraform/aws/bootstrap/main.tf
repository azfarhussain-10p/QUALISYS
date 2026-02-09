# Bootstrap: Terraform State Backend Resources
# Story: 0-1 Cloud Account & IAM Setup
# AC: 7 - S3 bucket with versioning + DynamoDB for state locking
#
# This must be applied FIRST with local state to create the remote backend.
# After applying, run `terraform init` in the parent directory to migrate to remote state.
#
# Usage:
#   cd infrastructure/terraform/bootstrap
#   terraform init
#   terraform apply -var="budget_alert_email=devops@qualisys.dev"
#
# After bootstrap completes:
#   cd ../
#   terraform init

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "QUALISYS"
      Environment = "management"
      ManagedBy   = "Terraform-Bootstrap"
      Owner       = "DevOps"
    }
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "qualisys"
}

data "aws_caller_identity" "current" {}

# S3 Bucket for Terraform State (AC7)
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_name}-terraform-state"

  lifecycle {
    prevent_destroy = true
  }
}

# Enable versioning on state bucket (AC7)
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption AES-256 (AC7 subtask 5.2)
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Block all public access to state bucket
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB table for state locking (AC7 subtask 5.3)
# Prevents concurrent Terraform modifications (Pre-mortem finding)
resource "aws_dynamodb_table" "terraform_state_lock" {
  name         = "terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

# Bucket policy: restrict access to DevOps role only (AC7 subtask 5.4)
resource "aws_s3_bucket_policy" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyNonDevOpsAccess"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:*"
        Resource = [
          aws_s3_bucket.terraform_state.arn,
          "${aws_s3_bucket.terraform_state.arn}/*"
        ]
        Condition = {
          StringNotLike = {
            "aws:PrincipalArn" = [
              "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/QualisysDevOpsAdmin",
              "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
            ]
          }
        }
      }
    ]
  })
}

output "state_bucket_name" {
  description = "Terraform state S3 bucket name"
  value       = aws_s3_bucket.terraform_state.id
}

output "state_bucket_arn" {
  description = "Terraform state S3 bucket ARN"
  value       = aws_s3_bucket.terraform_state.arn
}

output "lock_table_name" {
  description = "DynamoDB state lock table name"
  value       = aws_dynamodb_table.terraform_state_lock.name
}
