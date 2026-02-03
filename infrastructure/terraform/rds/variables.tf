# RDS Variables
# Story: 0-4 PostgreSQL Multi-Tenant Database

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"

  validation {
    condition     = can(regex("^1[5-9]\\.", var.db_engine_version))
    error_message = "PostgreSQL version must be 15 or higher."
  }
}

variable "db_instance_class_override" {
  description = "Override instance class (defaults to db.t3.medium for dev/staging, db.r5.large for production)"
  type        = string
  default     = ""
}

variable "db_allocated_storage" {
  description = "Initial allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum storage for autoscaling in GB"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Name of the initial database to create"
  type        = string
  default     = "qualisys_master"
}

variable "db_master_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "qualisys_admin"
}

variable "db_backup_retention_period" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}

variable "db_backup_window" {
  description = "Preferred backup window in UTC (must not overlap with maintenance window)"
  type        = string
  default     = "03:00-04:00"
}

variable "db_maintenance_window" {
  description = "Preferred maintenance window in UTC"
  type        = string
  default     = "Sun:04:00-Sun:05:00"
}

variable "db_max_connections" {
  description = "Maximum number of database connections"
  type        = number
  default     = 200
}

variable "db_performance_insights_retention" {
  description = "Performance Insights data retention in days (7 for free tier, up to 731)"
  type        = number
  default     = 7
}

variable "db_enhanced_monitoring_interval" {
  description = "Enhanced Monitoring interval in seconds (0 to disable, valid: 1, 5, 10, 15, 30, 60)"
  type        = number
  default     = 60
}

# NOTE: Secret rotation (90-day) requires a rotation Lambda function.
# The rotation_rules block will be added to the secret resource when the
# rotation Lambda is deployed (runtime step, not managed by Terraform here).
