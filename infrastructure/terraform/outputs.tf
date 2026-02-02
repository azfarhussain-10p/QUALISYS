# Outputs
# Story: 0-1 Cloud Account & IAM Setup

output "devops_admin_role_arn" {
  description = "ARN of the QualisysDevOpsAdmin role"
  value       = aws_iam_role.devops_admin.arn
}

output "developer_role_arn" {
  description = "ARN of the QualisysDeveloper role"
  value       = aws_iam_role.developer.arn
}

output "cicd_role_arn" {
  description = "ARN of the QualisysCICD role"
  value       = aws_iam_role.cicd.arn
}

# NOTE: EKS service role ARN output moved to eks/outputs.tf (Story 0.3)
# as eks_cluster_role_arn. EKS IAM resources now co-located in eks/iam.tf.

output "rds_service_role_arn" {
  description = "ARN of the RDS service account role"
  value       = aws_iam_role.rds_service.arn
}

output "elasticache_service_role_arn" {
  description = "ARN of the ElastiCache service account role"
  value       = aws_iam_role.elasticache_service.arn
}

output "ecr_service_role_arn" {
  description = "ARN of the ECR service account role"
  value       = aws_iam_role.ecr_service.arn
}

output "cloudtrail_bucket_name" {
  description = "S3 bucket name for CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail_logs.id
}

output "budget_sns_topic_arn" {
  description = "ARN of the SNS topic for budget alerts"
  value       = aws_sns_topic.budget_alerts.arn
}
