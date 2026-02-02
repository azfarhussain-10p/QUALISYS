# EKS Outputs
# Story: 0-3 Kubernetes Cluster Provisioning
# These outputs are consumed by downstream stories:
#   - Story 0.7 (Secret Management): cluster_oidc_provider_arn for IRSA
#   - Story 0.8-0.12 (CI/CD): cluster_endpoint, cluster_name
#   - Story 0.13 (Load Balancer): alb_controller_role_arn
#   - Story 0.19 (Monitoring): cluster_name, monitoring namespace

# =============================================================================
# Cluster
# =============================================================================

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "Endpoint URL for the EKS cluster API server"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_certificate_authority" {
  description = "Base64 encoded certificate authority data for the cluster"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

output "cluster_version" {
  description = "Kubernetes version of the EKS cluster"
  value       = aws_eks_cluster.main.version
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

# =============================================================================
# OIDC Provider (for IRSA)
# =============================================================================

output "cluster_oidc_provider_arn" {
  description = "ARN of the OIDC provider for IRSA"
  value       = aws_iam_openid_connect_provider.eks.arn
}

output "cluster_oidc_provider_url" {
  description = "URL of the OIDC provider (without https://)"
  value       = replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")
}

# =============================================================================
# IAM Roles
# =============================================================================

output "eks_cluster_role_arn" {
  description = "ARN of the EKS cluster IAM role"
  value       = aws_iam_role.eks_service.arn
}

output "eks_node_role_arn" {
  description = "ARN of the EKS node group IAM role"
  value       = aws_iam_role.eks_node.arn
}

output "cluster_autoscaler_role_arn" {
  description = "ARN of the cluster autoscaler IRSA role"
  value       = aws_iam_role.cluster_autoscaler.arn
}

output "alb_controller_role_arn" {
  description = "ARN of the ALB controller IRSA role"
  value       = aws_iam_role.alb_controller.arn
}

# =============================================================================
# Node Groups
# =============================================================================

output "general_node_group_name" {
  description = "Name of the general node group"
  value       = aws_eks_node_group.general.node_group_name
}

output "playwright_node_group_name" {
  description = "Name of the playwright-pool node group"
  value       = aws_eks_node_group.playwright.node_group_name
}

# =============================================================================
# Logging
# =============================================================================

output "cluster_log_group_name" {
  description = "CloudWatch Log Group name for EKS cluster logs"
  value       = aws_cloudwatch_log_group.eks_cluster.name
}
