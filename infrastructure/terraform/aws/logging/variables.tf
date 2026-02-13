# Variables for QUALISYS Logging Module (AWS)
# Story: 0-20 Log Aggregation

variable "eks_oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider for IRSA"
  type        = string
}

variable "eks_oidc_provider" {
  description = "EKS OIDC provider URL (without https://)"
  type        = string
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for log-based alert notifications (optional)"
  type        = string
  default     = ""
  sensitive   = true
}
