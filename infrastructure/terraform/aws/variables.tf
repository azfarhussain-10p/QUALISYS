# Environment Variables
# Story: 0-1 Cloud Account & IAM Setup

variable "aws_region" {
  description = "AWS region for infrastructure deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "qualisys"
}

variable "account_alias" {
  description = "AWS account alias for identification"
  type        = string
  default     = "qualisys-main"
}

variable "budget_alert_email" {
  description = "Email address for budget alert notifications"
  type        = string
}

variable "cloudtrail_retention_days" {
  description = "CloudTrail log retention in days"
  type        = number
  default     = 90
}
