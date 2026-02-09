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

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.29"
}

variable "vnet_subnet_id" {
  description = "Subnet ID for AKS nodes"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for monitoring"
  type        = string
}

# General node pool
variable "general_node_vm_size" {
  description = "VM size for general node pool"
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

# Playwright node pool
variable "playwright_node_vm_size" {
  description = "VM size for Playwright node pool"
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

variable "playwright_use_spot" {
  description = "Use spot instances for Playwright pool"
  type        = bool
  default     = false
}

variable "authorized_ip_ranges" {
  description = "Authorized IP ranges for API server access (production)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
