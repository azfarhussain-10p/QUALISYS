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

variable "address_space" {
  description = "Address space for the VNet"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "public_subnet_cidr" {
  description = "CIDR for public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "aks_subnet_cidr" {
  description = "CIDR for AKS subnet"
  type        = string
  default     = "10.0.10.0/22"
}

variable "postgresql_subnet_cidr" {
  description = "CIDR for PostgreSQL subnet"
  type        = string
  default     = "10.0.20.0/24"
}

variable "redis_subnet_cidr" {
  description = "CIDR for Redis subnet"
  type        = string
  default     = "10.0.21.0/24"
}

variable "appgw_subnet_cidr" {
  description = "CIDR for Application Gateway subnet"
  type        = string
  default     = "10.0.2.0/24"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
