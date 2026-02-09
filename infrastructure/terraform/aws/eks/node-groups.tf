# EKS Node Groups
# Story: 0-3 Kubernetes Cluster Provisioning
# AC: 2 - Node groups created: General (t3.medium, 2-10 nodes), Playwright Pool (c5.xlarge, 5-20 nodes)

# =============================================================================
# Launch Template (Task 2.6 - IMDSv2 required)
# =============================================================================

resource "aws_launch_template" "general" {
  name_prefix = "${var.project_name}-general-"

  # Task 2.6 - IMDSv2 required (prevents SSRF attacks to metadata service)
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"  # Enforces IMDSv2
    http_put_response_hop_limit = 1
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name      = "${var.project_name}-general-node"
      NodeGroup = "general"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_launch_template" "playwright" {
  name_prefix = "${var.project_name}-playwright-"

  # Task 2.6 - IMDSv2 required
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name      = "${var.project_name}-playwright-node"
      NodeGroup = "playwright-pool"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# General Node Group (Task 2.1, 2.4, 2.5)
# =============================================================================

resource "aws_eks_node_group" "general" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-general"
  node_role_arn   = aws_iam_role.eks_node.arn

  # Task 2.4 - Use private subnets
  subnet_ids = aws_subnet.private[*].id

  # Task 2.1 - t3.medium, min 2, max 10, desired 2
  instance_types = var.general_node_instance_types

  scaling_config {
    min_size     = var.general_node_min_size
    max_size     = var.general_node_max_size
    desired_size = var.general_node_desired_size
  }

  # Task 2.5 - Node labels
  labels = {
    "node-type" = "general"
  }

  launch_template {
    id      = aws_launch_template.general.id
    version = aws_launch_template.general.latest_version
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_ecr_read_policy,
  ]

  tags = {
    Name = "${var.project_name}-general-node-group"
  }
}

# =============================================================================
# Playwright Pool Node Group (Tasks 2.2, 2.3, 2.4, 2.5)
# =============================================================================

resource "aws_eks_node_group" "playwright" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-playwright-pool"
  node_role_arn   = aws_iam_role.eks_node.arn

  # Task 2.4 - Use private subnets
  subnet_ids = aws_subnet.private[*].id

  # Task 2.2 - c5.xlarge, min 5, max 20, desired 5
  instance_types = var.playwright_node_instance_types
  capacity_type  = var.playwright_use_spot ? "SPOT" : "ON_DEMAND"

  scaling_config {
    min_size     = var.playwright_node_min_size
    max_size     = var.playwright_node_max_size
    desired_size = var.playwright_node_desired_size
  }

  # Task 2.5 - Node labels
  labels = {
    "node-type" = "playwright"
  }

  # Task 2.3 - Taint: workload=playwright:NoSchedule
  taint {
    key    = "workload"
    value  = "playwright"
    effect = "NO_SCHEDULE"
  }

  launch_template {
    id      = aws_launch_template.playwright.id
    version = aws_launch_template.playwright.latest_version
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_ecr_read_policy,
  ]

  tags = {
    Name = "${var.project_name}-playwright-pool-node-group"
  }
}
