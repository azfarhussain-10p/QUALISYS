# Security Group Definitions
# Story: 0-2 VPC & Network Configuration
# AC: 6 - Security groups: ALB-SG, K8s-Nodes-SG, RDS-SG, ElastiCache-SG
# Constraint: Use SG-to-SG references, NOT IP-based rules

# =============================================================================
# ALB Security Group (Task 6.1)
# Inbound: HTTP (80) and HTTPS (443) from anywhere
# Outbound: All traffic to K8s Nodes
# =============================================================================

resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-alb-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "alb_ingress_http" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from internet"
}

resource "aws_security_group_rule" "alb_ingress_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from internet"
}

resource "aws_security_group_rule" "alb_egress_to_k8s" {
  type                     = "egress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = aws_security_group.k8s_nodes.id
  security_group_id        = aws_security_group.alb.id
  description              = "All traffic to K8s nodes"
}

# =============================================================================
# Kubernetes Nodes Security Group (Task 6.2)
# Inbound: All from ALB-SG, All from self (inter-node)
# Outbound: All to 0.0.0.0/0
# =============================================================================

resource "aws_security_group" "k8s_nodes" {
  name_prefix = "${var.project_name}-k8s-nodes-"
  description = "Security group for Kubernetes worker nodes"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-k8s-nodes-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "k8s_ingress_from_alb" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.k8s_nodes.id
  description              = "All traffic from ALB"
}

resource "aws_security_group_rule" "k8s_ingress_self" {
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  self              = true
  security_group_id = aws_security_group.k8s_nodes.id
  description       = "Inter-node communication"
}

resource "aws_security_group_rule" "k8s_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.k8s_nodes.id
  description       = "All outbound traffic"
}

# =============================================================================
# RDS Security Group (Task 6.3)
# Inbound: PostgreSQL (5432) from K8s Nodes ONLY
# Outbound: None (database-initiated connections not needed)
# =============================================================================

resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  description = "Security group for RDS PostgreSQL - access from K8s nodes only"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-rds-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "rds_ingress_from_k8s" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.k8s_nodes.id
  security_group_id        = aws_security_group.rds.id
  description              = "PostgreSQL from K8s nodes only"
}

# =============================================================================
# ElastiCache Security Group (Task 6.4)
# Inbound: Redis (6379) from K8s Nodes ONLY
# Outbound: None (cache-initiated connections not needed)
# =============================================================================

resource "aws_security_group" "elasticache" {
  name_prefix = "${var.project_name}-elasticache-"
  description = "Security group for ElastiCache Redis - access from K8s nodes only"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-elasticache-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "elasticache_ingress_from_k8s" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.k8s_nodes.id
  security_group_id        = aws_security_group.elasticache.id
  description              = "Redis from K8s nodes only"
}
