# Azure Key Vault Secrets — Variables
# Story: 0-22 Third-Party Service Accounts & API Keys

variable "project_name" {
  description = "Project name prefix for resource naming"
  type        = string
  default     = "qualisys"
}

variable "location" {
  description = "Azure region for Key Vault"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for Key Vault"
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

variable "allowed_ip_ranges" {
  description = "IP ranges allowed to access Key Vault (for VPN/office access)"
  type        = list(string)
  default     = []
}

variable "app_identity_principal_id" {
  description = "Principal ID of the application managed identity (for Key Vault access)"
  type        = string
  default     = ""
}
