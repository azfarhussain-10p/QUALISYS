# RDS PostgreSQL Instance
# Story: 0-4 PostgreSQL Multi-Tenant Database
# AC: 1 - PostgreSQL 15+ RDS instance created
# AC: 2 - Instance class per environment
# AC: 3 - Multi-AZ for production
# AC: 5 - Encryption at rest with KMS

# =============================================================================
# Locals — Environment-Dependent Configuration
# =============================================================================

locals {
  is_production = var.environment == "production"

  # AC2: db.t3.medium (dev/staging), db.r5.large (production)
  db_instance_class = (
    var.db_instance_class_override != ""
    ? var.db_instance_class_override
    : (local.is_production ? "db.r5.large" : "db.t3.medium")
  )

  # AC3: Multi-AZ for production only
  db_multi_az = local.is_production

  # Task 2.4: Deletion protection for production
  db_deletion_protection = local.is_production
}

# =============================================================================
# KMS Key for RDS Encryption (Task 1.5, AC5)
# =============================================================================

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS PostgreSQL encryption at rest"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-rds-encryption-key"
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project_name}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# =============================================================================
# Enhanced Monitoring IAM Role (Task 4.4)
# =============================================================================

resource "aws_iam_role" "rds_monitoring" {
  name        = "${var.project_name}-rds-enhanced-monitoring"
  description = "IAM role for RDS Enhanced Monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-rds-monitoring-role"
  }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# =============================================================================
# RDS PostgreSQL Instance (Tasks 1.1-1.6, 2.1-2.4, 4.1-4.4)
# =============================================================================

resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-db"

  # Task 1.2 - PostgreSQL 15+ (AC1)
  engine         = "postgres"
  engine_version = var.db_engine_version

  # Task 1.3 - Instance class per environment (AC2)
  instance_class = local.db_instance_class

  # Task 1.4 - Multi-AZ for production (AC3)
  multi_az = local.db_multi_az

  # Task 1.6 - Storage autoscaling
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"

  # Task 1.5 - Encryption at rest with KMS (AC5)
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  # Database configuration (AC7)
  db_name  = var.db_name
  username = var.db_master_username
  password = random_password.db_master.result

  # Task 1.1 - Use database subnets from Story 0.2
  db_subnet_group_name = aws_db_subnet_group.database.name

  # Task 4.1 - RDS security group from Story 0.2 (allows 5432 from K8s nodes)
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Task 4.2 - No public access
  publicly_accessible = false

  # Task 3.7 - Associate custom parameter group (AC6)
  parameter_group_name = aws_db_parameter_group.postgres15.name

  # Task 2.1 - Backup retention (AC4)
  backup_retention_period = var.db_backup_retention_period

  # Task 2.2 - Backup window (AC4)
  preferred_backup_window = var.db_backup_window

  # Task 2.3 - Maintenance window
  preferred_maintenance_window = var.db_maintenance_window

  # Task 2.4 - Deletion protection for production
  deletion_protection = local.db_deletion_protection

  # Task 4.3 - Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = var.db_performance_insights_retention
  performance_insights_kms_key_id       = aws_kms_key.rds.arn

  # Task 4.4 - Enhanced Monitoring (60-second granularity)
  monitoring_interval = var.db_enhanced_monitoring_interval
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # Prevent accidental data loss
  skip_final_snapshot       = !local.is_production
  final_snapshot_identifier = local.is_production ? "${var.project_name}-db-final-snapshot" : null
  copy_tags_to_snapshot     = true

  # Auto minor version upgrades
  auto_minor_version_upgrade = true

  tags = {
    Name = "${var.project_name}-db"
  }

  depends_on = [
    aws_iam_role_policy_attachment.rds_monitoring,
  ]
}
