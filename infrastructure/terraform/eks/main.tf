# EKS Cluster
# Story: 0-3 Kubernetes Cluster Provisioning
# AC: 1 - EKS cluster created with managed control plane (Kubernetes 1.28+)
# AC: 10 - Cluster logging enabled to CloudWatch

# =============================================================================
# CloudWatch Log Group for EKS Control Plane Logs (Task 1.4)
# =============================================================================

resource "aws_cloudwatch_log_group" "eks_cluster" {
  name              = "/aws/eks/${var.project_name}-eks/cluster"
  retention_in_days = var.cluster_log_retention_days

  tags = {
    Name = "${var.project_name}-eks-cluster-logs"
  }
}

# =============================================================================
# EKS Cluster (Tasks 1.1 - 1.5)
# =============================================================================

resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-eks"
  version  = var.cluster_version
  role_arn = aws_iam_role.eks_service.arn

  # Task 1.2 - Use private subnets from Story 0.2
  # Task 1.5 - Cluster security group managed by EKS
  vpc_config {
    subnet_ids              = aws_subnet.private[*].id
    endpoint_private_access = var.cluster_endpoint_private_access  # Task 1.3
    endpoint_public_access  = var.cluster_endpoint_public_access
    security_group_ids      = [aws_security_group.k8s_nodes.id]
  }

  # Task 1.4 - Enable cluster logging (api, audit, authenticator, controllerManager, scheduler)
  enabled_cluster_log_types = var.cluster_log_types

  # Encryption configuration for secrets at rest
  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_vpc_resource_controller,
    aws_cloudwatch_log_group.eks_cluster,
  ]

  tags = {
    Name = "${var.project_name}-eks"
  }
}

# =============================================================================
# KMS Key for EKS Secrets Encryption
# =============================================================================

resource "aws_kms_key" "eks" {
  description             = "KMS key for EKS cluster secrets encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-eks-secrets-key"
  }
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${var.project_name}-eks-secrets"
  target_key_id = aws_kms_key.eks.key_id
}

# =============================================================================
# OIDC Provider for IRSA (IAM Roles for Service Accounts)
# =============================================================================

data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer

  tags = {
    Name = "${var.project_name}-eks-oidc"
  }
}

# =============================================================================
# EKS Addons
# =============================================================================

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"

  resolve_conflicts_on_update = "OVERWRITE"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"

  resolve_conflicts_on_update = "OVERWRITE"
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"

  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [
    aws_eks_node_group.general,
  ]
}
