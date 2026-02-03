# ECR Outputs
# Story: 0-6 Container Registry
# These outputs are consumed by downstream stories:
#   - Story 0.8 (GitHub Actions): ECR repository URLs for image push
#   - Story 0.9 (Docker Build): ECR authentication and push targets
#   - Story 0.3 (K8s): Node IAM role needs ECR pull permissions

# =============================================================================
# Repository URLs
# =============================================================================

output "ecr_repository_urls" {
  description = "Map of repository names to URLs"
  value       = { for k, v in aws_ecr_repository.repos : k => v.repository_url }
}

output "ecr_repository_arns" {
  description = "Map of repository names to ARNs"
  value       = { for k, v in aws_ecr_repository.repos : k => v.arn }
}

output "ecr_registry_id" {
  description = "The registry ID (AWS account ID)"
  value       = values(aws_ecr_repository.repos)[0].registry_id
}

# =============================================================================
# Individual Repository URLs (convenience outputs for downstream consumers)
# =============================================================================

output "ecr_api_repository_url" {
  description = "URL of the qualisys-api ECR repository"
  value       = aws_ecr_repository.repos["qualisys-api"].repository_url
}

output "ecr_web_repository_url" {
  description = "URL of the qualisys-web ECR repository"
  value       = aws_ecr_repository.repos["qualisys-web"].repository_url
}

output "ecr_playwright_repository_url" {
  description = "URL of the playwright-runner ECR repository"
  value       = aws_ecr_repository.repos["playwright-runner"].repository_url
}
