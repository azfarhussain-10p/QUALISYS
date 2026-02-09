# AWS Budget Alerts and Anomaly Detection
# Story: 0-1 Cloud Account & IAM Setup
# AC: 8 - Budget alerts at $500, $1000, $2000 thresholds
# AC: 10 - Anomaly detection at 150% of forecast threshold

# SNS Topic for budget alert notifications (Task 6.5)
resource "aws_sns_topic" "budget_alerts" {
  name = "qualisys-budget-alerts"
}

resource "aws_sns_topic_subscription" "budget_email" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.budget_alert_email
}

# Budget: $500 threshold (AC8 - Task 6.1)
resource "aws_budgets_budget" "monthly_500" {
  name         = "qualisys-monthly-500"
  budget_type  = "COST"
  limit_amount = "500"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# Budget: $1000 threshold (AC8 - Task 6.2)
resource "aws_budgets_budget" "monthly_1000" {
  name         = "qualisys-monthly-1000"
  budget_type  = "COST"
  limit_amount = "1000"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# Budget: $2000 threshold (AC8 - Task 6.3)
resource "aws_budgets_budget" "monthly_2000" {
  name         = "qualisys-monthly-2000"
  budget_type  = "COST"
  limit_amount = "2000"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# Budget Anomaly Detection at 150% of forecast (AC10 - Task 6.4)
resource "aws_budgets_budget" "anomaly_detection" {
  name         = "qualisys-anomaly-detection"
  budget_type  = "COST"
  limit_amount = "2000"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 150
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# Cost Anomaly Monitor for additional detection
resource "aws_ce_anomaly_monitor" "qualisys" {
  name              = "qualisys-cost-anomaly-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "qualisys" {
  name      = "qualisys-cost-anomaly-alerts"
  frequency = "DAILY"

  monitor_arn_list = [aws_ce_anomaly_monitor.qualisys.arn]

  subscriber {
    type    = "SNS"
    address = aws_sns_topic.budget_alerts.arn
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = ["50"]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
}
