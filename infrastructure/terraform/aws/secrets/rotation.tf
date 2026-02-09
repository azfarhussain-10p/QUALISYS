# Secret Rotation Configuration
# Story: 0-7 Secret Management
# AC: 10 - Database password rotation every 90 days
# Tasks 5.1-5.5

# =============================================================================
# Rotation Lambda Security Group (Task 5.1)
# Lambda runs in private subnets (NAT access for Secrets Manager API).
# Needs egress to RDS (port 5432) and Secrets Manager (HTTPS via NAT).
# =============================================================================

resource "aws_security_group" "rotation_lambda" {
  name_prefix = "${var.project_name}-rotation-lambda-"
  vpc_id      = aws_vpc.main.id
  description = "Security group for Secrets Manager rotation Lambda"

  # Egress to RDS for password change
  egress {
    description     = "PostgreSQL access to RDS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.rds.id]
  }

  # Egress to Secrets Manager API via NAT Gateway
  egress {
    description = "HTTPS for Secrets Manager API (via NAT)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rotation-lambda-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Allow rotation Lambda to reach RDS instance
resource "aws_security_group_rule" "rds_from_rotation_lambda" {
  description              = "PostgreSQL from rotation Lambda"
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.rotation_lambda.id
  security_group_id        = aws_security_group.rds.id
}

# =============================================================================
# Rotation Lambda via AWS Serverless Application Repository (Task 5.1)
# Uses the AWS-managed SecretsManagerRDSPostgreSQLRotationSingleUser template.
# This Lambda handles the 4-step rotation process:
#   createSecret → setSecret → testSecret → finishSecret
# =============================================================================

data "aws_serverlessapplicationrepository_application" "db_rotation" {
  application_id = "arn:aws:serverlessrepo:us-east-1:297356227824:applications/SecretsManagerRDSPostgreSQLRotationSingleUser"
}

resource "aws_serverlessapplicationrepository_cloudformation_stack" "db_rotation" {
  name           = "${var.project_name}-db-rotation"
  application_id = data.aws_serverlessapplicationrepository_application.db_rotation.application_id
  capabilities   = data.aws_serverlessapplicationrepository_application.db_rotation.required_capabilities

  semantic_version = data.aws_serverlessapplicationrepository_application.db_rotation.semantic_version

  parameters = {
    endpoint            = "https://secretsmanager.${var.aws_region}.amazonaws.com"
    functionName        = "${var.project_name}-db-password-rotation"
    vpcSubnetIds        = join(",", aws_subnet.private[*].id)
    vpcSecurityGroupIds = aws_security_group.rotation_lambda.id
  }

  tags = {
    Name = "${var.project_name}-db-rotation-stack"
  }
}

# =============================================================================
# Rotation Schedule (AC10 - Tasks 5.2)
# Configures automatic rotation on the database connection secret.
# The rotation Lambda is created by the SAR CloudFormation stack above.
# =============================================================================

resource "aws_secretsmanager_secret_rotation" "database" {
  secret_id           = aws_secretsmanager_secret.db_connection.id
  rotation_lambda_arn = aws_serverlessapplicationrepository_cloudformation_stack.db_rotation.outputs["RotationLambdaARN"]

  rotation_rules {
    automatically_after_days = var.db_rotation_days
  }
}

# =============================================================================
# Rotation Notifications (Task 5.5)
# SNS topic for rotation events (success, failure).
# =============================================================================

resource "aws_sns_topic" "secrets_alerts" {
  name = "${var.project_name}-secrets-alerts"

  tags = {
    Name = "${var.project_name}-secrets-alerts"
  }
}

# EventBridge rule to capture rotation events
# Rotation lifecycle events use "AWS API Call via CloudTrail" with RotateSecret,
# plus Secrets Manager publishes dedicated rotation status events.
resource "aws_cloudwatch_event_rule" "rotation_events" {
  name        = "${var.project_name}-secret-rotation-events"
  description = "Capture Secrets Manager rotation API calls"

  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventSource = ["secretsmanager.amazonaws.com"]
      eventName   = ["RotateSecret"]
    }
  })

  tags = {
    Name = "${var.project_name}-rotation-events"
  }
}

resource "aws_cloudwatch_event_target" "rotation_events_sns" {
  rule      = aws_cloudwatch_event_rule.rotation_events.name
  target_id = "rotation-sns-alert"
  arn       = aws_sns_topic.secrets_alerts.arn
}

resource "aws_sns_topic_policy" "secrets_alerts" {
  arn = aws_sns_topic.secrets_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.secrets_alerts.arn
      }
    ]
  })
}
