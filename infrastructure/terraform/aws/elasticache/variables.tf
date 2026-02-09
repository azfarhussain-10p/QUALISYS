# ElastiCache Variables
# Story: 0-5 Redis Caching Layer

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"

  validation {
    condition     = can(regex("^7\\.", var.redis_engine_version))
    error_message = "Redis version must be 7.0 or higher."
  }
}

variable "redis_node_type_override" {
  description = "Override node type (defaults to cache.t3.micro for dev, cache.t3.small for staging, cache.r5.large for production)"
  type        = string
  default     = ""
}

variable "redis_snapshot_retention_days" {
  description = "Number of days to retain automatic snapshots (0 to disable)"
  type        = number
  default     = 7
}

variable "redis_snapshot_window" {
  description = "Preferred snapshot window in UTC (must not overlap with maintenance window)"
  type        = string
  default     = "05:00-06:00"
}

variable "redis_maintenance_window" {
  description = "Preferred maintenance window in UTC"
  type        = string
  default     = "Sun:06:00-Sun:07:00"
}
