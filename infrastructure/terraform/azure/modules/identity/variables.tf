variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "resource_group_id" {
  description = "ID of the resource group"
  type        = string
}

variable "aks_oidc_issuer_url" {
  description = "OIDC issuer URL from AKS cluster (for Workload Identity)"
  type        = string
}

variable "key_vault_id" {
  description = "ID of the Key Vault for role assignments"
  type        = string
}

variable "acr_id" {
  description = "ID of the ACR for CI/CD push role"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
