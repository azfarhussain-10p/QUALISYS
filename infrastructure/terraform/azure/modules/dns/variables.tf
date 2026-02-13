# DNS Variables - Azure DNS
# Story: 0-13 Load Balancer & Ingress Configuration

variable "resource_group_name" {
  description = "Resource group for DNS zones"
  type        = string
}

variable "ingress_public_ip_id" {
  description = "Azure Public IP resource ID for the NGINX Ingress Controller load balancer"
  type        = string
}

variable "production_domain" {
  description = "Production domain name"
  type        = string
  default     = "qualisys.io"
}

variable "staging_domain" {
  description = "Staging domain name"
  type        = string
  default     = "qualisys.dev"
}
