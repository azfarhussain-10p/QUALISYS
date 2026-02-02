# EKS Variables
# Story: 0-3 Kubernetes Cluster Provisioning

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"

  validation {
    condition     = can(regex("^1\\.(2[8-9]|[3-9][0-9])$", var.cluster_version))
    error_message = "Cluster version must be 1.28 or higher."
  }
}

variable "cluster_endpoint_private_access" {
  description = "Enable private API server endpoint access"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access" {
  description = "Enable public API server endpoint access"
  type        = bool
  default     = true
}

variable "cluster_log_types" {
  description = "EKS control plane log types to enable"
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

variable "cluster_log_retention_days" {
  description = "CloudWatch log retention for EKS cluster logs"
  type        = number
  default     = 30
}

# -----------------------------------------------------------------------------
# Node Group: General
# -----------------------------------------------------------------------------

variable "general_node_instance_types" {
  description = "Instance types for the general node group"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "general_node_min_size" {
  description = "Minimum number of nodes in the general node group"
  type        = number
  default     = 2
}

variable "general_node_max_size" {
  description = "Maximum number of nodes in the general node group"
  type        = number
  default     = 10
}

variable "general_node_desired_size" {
  description = "Desired number of nodes in the general node group"
  type        = number
  default     = 2
}

# -----------------------------------------------------------------------------
# Node Group: Playwright Pool
# -----------------------------------------------------------------------------

variable "playwright_node_instance_types" {
  description = "Instance types for the playwright-pool node group"
  type        = list(string)
  default     = ["c5.xlarge"]
}

variable "playwright_node_min_size" {
  description = "Minimum number of nodes in the playwright-pool node group"
  type        = number
  default     = 5
}

variable "playwright_node_max_size" {
  description = "Maximum number of nodes in the playwright-pool node group"
  type        = number
  default     = 20
}

variable "playwright_node_desired_size" {
  description = "Desired number of nodes in the playwright-pool node group"
  type        = number
  default     = 5
}

variable "playwright_use_spot" {
  description = "Use spot instances for playwright-pool (cost optimization)"
  type        = bool
  default     = false
}

# NOTE: Namespace resource quotas are defined in Kubernetes YAML manifests
# at infrastructure/kubernetes/namespaces/resource-quotas.yaml
# (not managed via Terraform to avoid requiring the kubernetes provider)
