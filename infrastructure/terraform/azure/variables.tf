# Azure Environment Variables
# QUALISYS Azure Infrastructure

variable "azure_subscription_id" {
  description = "Azure subscription ID for infrastructure deployment"
  type        = string
}

variable "azure_location" {
  description = "Azure region for infrastructure deployment"
  type        = string
  default     = "eastus"
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

variable "budget_alert_email" {
  description = "Email address for budget alert notifications"
  type        = string
}

variable "log_retention_days" {
  description = "Log Analytics workspace retention in days"
  type        = number
  default     = 90
}

# --- VNet ---
variable "vnet_address_space" {
  description = "Address space for the Virtual Network"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

# --- AKS ---
variable "kubernetes_version" {
  description = "Kubernetes version for AKS cluster"
  type        = string
  default     = "1.29"
}

variable "general_node_vm_size" {
  description = "VM size for the general system node pool"
  type        = string
  default     = "Standard_D2s_v3"
}

variable "general_node_min_count" {
  description = "Minimum node count for general pool"
  type        = number
  default     = 2
}

variable "general_node_max_count" {
  description = "Maximum node count for general pool"
  type        = number
  default     = 10
}

variable "playwright_node_vm_size" {
  description = "VM size for the Playwright node pool"
  type        = string
  default     = "Standard_F4s_v2"
}

variable "playwright_node_min_count" {
  description = "Minimum node count for Playwright pool"
  type        = number
  default     = 5
}

variable "playwright_node_max_count" {
  description = "Maximum node count for Playwright pool"
  type        = number
  default     = 20
}

# --- PostgreSQL ---
variable "postgresql_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "15"
}

variable "postgresql_sku_name" {
  description = "SKU name for PostgreSQL Flexible Server (empty for environment-based default)"
  type        = string
  default     = ""
}

variable "postgresql_storage_mb" {
  description = "Storage in MB for PostgreSQL"
  type        = number
  default     = 32768
}

variable "postgresql_db_name" {
  description = "Name of the initial database"
  type        = string
  default     = "qualisys_master"
}

variable "postgresql_admin_username" {
  description = "Administrator username for PostgreSQL"
  type        = string
  default     = "qualisys_admin"
}

# --- Redis ---
variable "redis_capacity" {
  description = "Size of the Redis cache (0-6 for Basic/Standard, 1-5 for Premium)"
  type        = number
  default     = 1
}

variable "redis_family" {
  description = "Redis cache family (C for Basic/Standard, P for Premium)"
  type        = string
  default     = "P"
}

variable "redis_sku_name" {
  description = "Redis SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Premium"
}

# --- ACR ---
variable "acr_sku" {
  description = "SKU for Azure Container Registry"
  type        = string
  default     = "Premium"
}

# --- Key Vault ---
variable "secret_recovery_days" {
  description = "Number of days to retain deleted secrets (soft delete)"
  type        = number
  default     = 30
}
