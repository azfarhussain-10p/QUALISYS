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

variable "delegated_subnet_id" {
  description = "ID of the delegated subnet for PostgreSQL"
  type        = string
}

variable "private_dns_zone_id" {
  description = "ID of the private DNS zone for PostgreSQL"
  type        = string
}

variable "postgresql_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "15"
}

variable "sku_name" {
  description = "SKU name override (empty for environment-based default)"
  type        = string
  default     = ""
}

variable "storage_mb" {
  description = "Storage in MB"
  type        = number
  default     = 32768
}

variable "db_name" {
  description = "Name of the initial database"
  type        = string
  default     = "qualisys_master"
}

variable "admin_username" {
  description = "Administrator username"
  type        = string
  default     = "qualisys_admin"
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
