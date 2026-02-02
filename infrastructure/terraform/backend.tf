# Terraform Remote State Backend
# Story: 0-1 Cloud Account & IAM Setup
# AC: 7 - S3 bucket with versioning + DynamoDB for state locking
#
# IMPORTANT: Run bootstrap/main.tf first to create the S3 bucket and DynamoDB table.
# Then run `terraform init` in this directory to connect to the remote backend.
# Note: Backend block does not support variable interpolation — values must be hardcoded or
# supplied via -backend-config CLI flags.

terraform {
  backend "s3" {
    bucket         = "qualisys-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
