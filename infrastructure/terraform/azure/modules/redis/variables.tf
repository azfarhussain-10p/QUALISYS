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

variable "subnet_id" {
  description = "Subnet ID for VNet integration (Premium only)"
  type        = string
  default     = null
}

variable "capacity" {
  description = "Size of the Redis cache (0 for environment-based default)"
  type        = number
  default     = 0
}

variable "family" {
  description = "Redis cache family (C for Basic/Standard, P for Premium)"
  type        = string
  default     = "P"
}

variable "sku_name" {
  description = "Redis SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Premium"
}

variable "key_vault_id" {
  description = "Key Vault ID for storing credentials"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
