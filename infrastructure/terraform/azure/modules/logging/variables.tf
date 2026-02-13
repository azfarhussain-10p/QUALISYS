# Variables for QUALISYS Logging Module (Azure)
# Story: 0-20 Log Aggregation

variable "project_name" {
  description = "Project name prefix for resource naming"
  type        = string
  default     = "qualisys"
}

variable "location" {
  description = "Azure region for resources"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to deploy into"
  type        = string
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default     = {}
}

variable "aks_oidc_issuer_url" {
  description = "AKS OIDC issuer URL for Workload Identity federation"
  type        = string
}

variable "enable_cmk" {
  description = "Enable Customer-Managed Key encryption for Log Analytics (requires dedicated cluster)"
  type        = bool
  default     = false
}

variable "cmk_key_vault_key_id" {
  description = "Key Vault key ID for CMK encryption (required if enable_cmk = true)"
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Email address for log-based alert notifications (optional)"
  type        = string
  default     = ""
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for log-based alert notifications (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "log_reader_principal_id" {
  description = "Azure AD principal ID to grant Log Analytics Reader role (optional)"
  type        = string
  default     = ""
}
