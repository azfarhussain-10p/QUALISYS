# RDS Parameter Group
# Story: 0-4 PostgreSQL Multi-Tenant Database
# AC: 6 - Parameter group configured: max_connections=200, shared_buffers optimized
# Tasks 3.1-3.7

resource "aws_db_parameter_group" "postgres15" {
  name        = "${var.project_name}-postgres15"
  family      = "postgres15"
  description = "Custom parameter group for QUALISYS PostgreSQL 15"

  # Task 3.2 - max_connections = 200
  parameter {
    name  = "max_connections"
    value = var.db_max_connections
  }

  # Task 3.3 - shared_buffers = 25% of instance memory
  # DBInstanceClassMemory is in bytes; shared_buffers is in 8KB pages
  # 25% = DBInstanceClassMemory / (4 * 8192) = DBInstanceClassMemory / 32768
  parameter {
    name  = "shared_buffers"
    value = "{DBInstanceClassMemory/32768}"
  }

  # Task 3.4 - work_mem = 64MB (in KB)
  parameter {
    name  = "work_mem"
    value = "65536"
  }

  # Task 3.5 - maintenance_work_mem = 512MB (in KB)
  parameter {
    name  = "maintenance_work_mem"
    value = "524288"
  }

  # Task 3.6 - Enable pg_stat_statements for query monitoring
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
    # Requires reboot to take effect
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "pg_stat_statements.track"
    value = "all"
  }

  parameter {
    name  = "pg_stat_statements.max"
    value = "10000"
  }

  # Additional recommended settings for multi-tenant workloads
  parameter {
    name  = "effective_cache_size"
    value = "{DBInstanceClassMemory/16384}"  # 50% of RAM
  }

  parameter {
    name  = "random_page_cost"
    value = "1.1"  # Optimized for SSD storage (gp3)
  }

  # Logging for monitoring and troubleshooting
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking > 1 second
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  # RLS-related: ensure row security is enforced
  parameter {
    name  = "row_security"
    value = "on"
  }

  tags = {
    Name = "${var.project_name}-postgres15-params"
  }

  lifecycle {
    create_before_destroy = true
  }
}
