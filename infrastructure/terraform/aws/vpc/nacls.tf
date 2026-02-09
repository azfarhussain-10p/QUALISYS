# Network ACLs
# Story: 0-2 VPC & Network Configuration
# AC: 7 - Network ACLs for additional security layer

# =============================================================================
# Public Subnet NACL (Task 7.1)
# Allow HTTP, HTTPS, SSH inbound; ephemeral ports outbound
# =============================================================================

resource "aws_network_acl" "public" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.public[*].id  # Task 7.4

  # Inbound: HTTP
  ingress {
    rule_no    = 100
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 80
    to_port    = 80
  }

  # Inbound: HTTPS
  ingress {
    rule_no    = 110
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }

  # Inbound: Ephemeral ports (return traffic from internet)
  ingress {
    rule_no    = 120
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  # Inbound: Allow from VPC CIDR (internal traffic)
  ingress {
    rule_no    = 130
    protocol   = "-1"
    action     = "allow"
    cidr_block = var.vpc_cidr
    from_port  = 0
    to_port    = 0
  }

  # Outbound: All traffic
  egress {
    rule_no    = 100
    protocol   = "-1"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  tags = {
    Name = "${var.project_name}-public-nacl"
    Type = "public"
  }
}

# =============================================================================
# Private Subnet NACL (Task 7.2)
# Allow from VPC CIDR only
# =============================================================================

resource "aws_network_acl" "private" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.private[*].id  # Task 7.4

  # Inbound: All from VPC CIDR
  ingress {
    rule_no    = 100
    protocol   = "-1"
    action     = "allow"
    cidr_block = var.vpc_cidr
    from_port  = 0
    to_port    = 0
  }

  # Inbound: Ephemeral ports (return traffic from NAT Gateway / internet)
  ingress {
    rule_no    = 110
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  # Outbound: All traffic (to reach NAT Gateway and VPC resources)
  egress {
    rule_no    = 100
    protocol   = "-1"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  tags = {
    Name = "${var.project_name}-private-nacl"
    Type = "private"
  }
}

# =============================================================================
# Database Subnet NACL (Task 7.3)
# Allow PostgreSQL (5432) and Redis (6379) from private subnets ONLY
# =============================================================================

resource "aws_network_acl" "database" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.database[*].id  # Task 7.4

  # Inbound: PostgreSQL from private subnets (AZ-a)
  ingress {
    rule_no    = 100
    protocol   = "tcp"
    action     = "allow"
    cidr_block = var.private_subnet_cidrs[0]
    from_port  = 5432
    to_port    = 5432
  }

  # Inbound: PostgreSQL from private subnets (AZ-b)
  ingress {
    rule_no    = 110
    protocol   = "tcp"
    action     = "allow"
    cidr_block = var.private_subnet_cidrs[1]
    from_port  = 5432
    to_port    = 5432
  }

  # Inbound: Redis from private subnets (AZ-a)
  ingress {
    rule_no    = 120
    protocol   = "tcp"
    action     = "allow"
    cidr_block = var.private_subnet_cidrs[0]
    from_port  = 6379
    to_port    = 6379
  }

  # Inbound: Redis from private subnets (AZ-b)
  ingress {
    rule_no    = 130
    protocol   = "tcp"
    action     = "allow"
    cidr_block = var.private_subnet_cidrs[1]
    from_port  = 6379
    to_port    = 6379
  }

  # Inbound: Ephemeral ports (return traffic)
  ingress {
    rule_no    = 140
    protocol   = "tcp"
    action     = "allow"
    cidr_block = var.vpc_cidr
    from_port  = 1024
    to_port    = 65535
  }

  # Outbound: Ephemeral ports to private subnets (response traffic)
  egress {
    rule_no    = 100
    protocol   = "tcp"
    action     = "allow"
    cidr_block = var.vpc_cidr
    from_port  = 1024
    to_port    = 65535
  }

  tags = {
    Name = "${var.project_name}-database-nacl"
    Type = "database"
  }
}
