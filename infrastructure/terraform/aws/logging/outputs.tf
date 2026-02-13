# Outputs for QUALISYS Logging Module (AWS)
# Story: 0-20 Log Aggregation

output "log_group_api_staging" {
  description = "CloudWatch log group name for staging API"
  value       = aws_cloudwatch_log_group.api_staging.name
}

output "log_group_api_production" {
  description = "CloudWatch log group name for production API"
  value       = aws_cloudwatch_log_group.api_production.name
}

output "log_group_worker_staging" {
  description = "CloudWatch log group name for staging worker"
  value       = aws_cloudwatch_log_group.worker_staging.name
}

output "log_group_worker_production" {
  description = "CloudWatch log group name for production worker"
  value       = aws_cloudwatch_log_group.worker_production.name
}

output "fluent_bit_role_arn" {
  description = "IRSA role ARN for Fluent Bit service account"
  value       = aws_iam_role.fluent_bit.arn
}

output "log_reader_policy_arn" {
  description = "IAM policy ARN for log reader access"
  value       = aws_iam_policy.log_reader.arn
}

output "log_alerts_sns_topic_arn" {
  description = "SNS topic ARN for log-based alerts"
  value       = aws_sns_topic.log_alerts.arn
}

output "kms_key_arn" {
  description = "KMS key ARN for CloudWatch Logs encryption"
  value       = aws_kms_key.logs.arn
}
