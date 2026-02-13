# DNS Variables - AWS Route 53
# Story: 0-13 Load Balancer & Ingress Configuration

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
