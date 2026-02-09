# Secrets Manager Variables
# Story: 0-7 Secret Management

variable "db_rotation_days" {
  description = "Days between automatic database password rotation"
  type        = number
  default     = 90

  validation {
    condition     = var.db_rotation_days >= 1 && var.db_rotation_days <= 365
    error_message = "Rotation period must be between 1 and 365 days."
  }
}

variable "secret_recovery_window_days" {
  description = "Days to recover a deleted secret before permanent deletion (0 = immediate)"
  type        = number
  default     = 30
}

variable "external_secrets_namespace" {
  description = "Kubernetes namespace for ExternalSecrets Operator"
  type        = string
  default     = "external-secrets"
}

variable "external_secrets_service_account" {
  description = "Kubernetes service account name for ExternalSecrets Operator"
  type        = string
  default     = "external-secrets-sa"
}
