# VPC Flow Logs
# Story: 0-2 VPC & Network Configuration
# AC: 8 - VPC Flow Logs enabled to CloudWatch for network traffic monitoring

# =============================================================================
# CloudWatch Log Group (Task 8.1, 8.4)
# =============================================================================

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/aws/vpc/${var.project_name}-flow-logs"  # Task 8.1
  retention_in_days = var.flow_log_retention_days               # Task 8.4 - 30 days

  tags = {
    Name = "${var.project_name}-vpc-flow-logs"
  }
}

# =============================================================================
# IAM Role for VPC Flow Logs (Task 8.2)
# =============================================================================

resource "aws_iam_role" "vpc_flow_logs" {
  name        = "${var.project_name}-vpc-flow-logs"
  description = "IAM role for VPC Flow Logs to write to CloudWatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "${var.project_name}-vpc-flow-logs-policy"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = "${aws_cloudwatch_log_group.vpc_flow_logs.arn}:*"
      }
    ]
  })
}

# =============================================================================
# VPC Flow Log (Task 8.3)
# ALL traffic, 10-minute aggregation interval
# =============================================================================

resource "aws_flow_log" "main" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"                                    # Task 8.3
  log_destination      = aws_cloudwatch_log_group.vpc_flow_logs.arn
  log_destination_type = "cloud-watch-logs"
  iam_role_arn         = aws_iam_role.vpc_flow_logs.arn
  max_aggregation_interval = 600                                  # 10-minute aggregation

  tags = {
    Name = "${var.project_name}-vpc-flow-log"
  }
}
