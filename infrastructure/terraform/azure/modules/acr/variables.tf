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

variable "sku" {
  description = "SKU for Azure Container Registry"
  type        = string
  default     = "Premium"
}

variable "aks_principal_id" {
  description = "Object ID of the AKS kubelet identity for ACR pull access"
  type        = string
}

variable "georeplications" {
  description = "Geo-replication locations for production"
  type = list(object({
    location        = string
    zone_redundancy = bool
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
