# CloudWatch Metric Filters and Alarms for Log-Based Alerts
# Story: 0-20 Log Aggregation (ELK or CloudWatch)
# AC: 9  - Error rate spike alert (>10 errors/min)
# AC: 10 - 5xx response rate alert (>5%)

# -----------------------------------------------------------------------------
# SNS Topic for log-based alerts (Task 5.5, 5.6)
# -----------------------------------------------------------------------------
resource "aws_sns_topic" "log_alerts" {
  name = "qualisys-log-alerts"

  tags = {
    Name    = "qualisys-log-alerts"
    Project = "qualisys"
  }
}

resource "aws_sns_topic_subscription" "slack" {
  count     = var.slack_webhook_url != "" ? 1 : 0
  topic_arn = aws_sns_topic.log_alerts.arn
  protocol  = "https"
  endpoint  = var.slack_webhook_url
}

# -----------------------------------------------------------------------------
# AC9: Error rate spike (>10 errors/min) — Task 5.1, 5.2
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_metric_filter" "error_count" {
  name           = "qualisys-error-count"
  pattern        = "{ $.level = \"error\" }"
  log_group_name = aws_cloudwatch_log_group.api_production.name

  metric_transformation {
    name          = "ErrorCount"
    namespace     = "QUALISYS/Application"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "error_rate_spike" {
  alarm_name          = "qualisys-error-rate-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ErrorCount"
  namespace           = "QUALISYS/Application"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Error rate exceeds 10 errors per minute (AC9)"
  alarm_actions       = [aws_sns_topic.log_alerts.arn]
  ok_actions          = [aws_sns_topic.log_alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Severity = "critical"
    Project  = "qualisys"
  }
}

# -----------------------------------------------------------------------------
# AC10: 5xx response rate >5% — Task 5.3, 5.4
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_metric_filter" "http_5xx" {
  name           = "qualisys-http-5xx"
  pattern        = "{ $.status >= 500 }"
  log_group_name = aws_cloudwatch_log_group.api_production.name

  metric_transformation {
    name          = "5xxCount"
    namespace     = "QUALISYS/Application"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "http_total" {
  name           = "qualisys-http-total"
  pattern        = "{ $.status = * }"
  log_group_name = aws_cloudwatch_log_group.api_production.name

  metric_transformation {
    name          = "RequestCount"
    namespace     = "QUALISYS/Application"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_5xx_rate" {
  alarm_name          = "qualisys-high-5xx-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  threshold           = 5
  alarm_description   = "5xx error rate exceeds 5% (AC10)"
  alarm_actions       = [aws_sns_topic.log_alerts.arn]
  ok_actions          = [aws_sns_topic.log_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "IF(total > 0, e5xx / total * 100, 0)"
    label       = "5xx Error Rate"
    return_data = true
  }

  metric_query {
    id = "e5xx"
    metric {
      metric_name = "5xxCount"
      namespace   = "QUALISYS/Application"
      period      = 60
      stat        = "Sum"
    }
  }

  metric_query {
    id = "total"
    metric {
      metric_name = "RequestCount"
      namespace   = "QUALISYS/Application"
      period      = 60
      stat        = "Sum"
    }
  }

  tags = {
    Severity = "critical"
    Project  = "qualisys"
  }
}
