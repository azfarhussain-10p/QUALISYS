# VPC, Subnets, and Internet Gateway
# Story: 0-2 VPC & Network Configuration
# AC: 1 - VPC with CIDR 10.0.0.0/16
# AC: 2 - 6 subnets across 2 AZs (public, private, database)
# AC: 3 - Internet Gateway attached to VPC

# =============================================================================
# VPC (AC1 - Task 1)
# =============================================================================

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true  # Task 1.2
  enable_dns_support   = true  # Task 1.2

  tags = {
    Name        = "${var.project_name}-vpc"  # Task 1.3
    Environment = "all"
  }
}

# =============================================================================
# Public Subnets (AC2 - Task 2.1)
# =============================================================================

resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true  # Task 2.5

  tags = {
    Name = "${var.project_name}-public-${var.availability_zones[count.index]}"
    Type = "public"
    # Required for EKS ALB controller auto-discovery
    "kubernetes.io/role/elb" = "1"
  }
}

# =============================================================================
# Private Subnets (AC2 - Task 2.2)
# =============================================================================

resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-private-${var.availability_zones[count.index]}"
    Type = "private"
    # Required for EKS internal ALB controller auto-discovery
    "kubernetes.io/role/internal-elb" = "1"
  }
}

# =============================================================================
# Database Subnets (AC2 - Task 2.3)
# =============================================================================

resource "aws_subnet" "database" {
  count = length(var.database_subnet_cidrs)

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.database_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-database-${var.availability_zones[count.index]}"
    Type = "database"
  }
}

# RDS Subnet Group (needed by Story 0.4 for RDS instance placement)
resource "aws_db_subnet_group" "database" {
  name       = "${var.project_name}-database"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name = "${var.project_name}-database-subnet-group"
  }
}

# ElastiCache Subnet Group (needed by Story 0.5 for Redis placement)
resource "aws_elasticache_subnet_group" "database" {
  name       = "${var.project_name}-elasticache"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name = "${var.project_name}-elasticache-subnet-group"
  }
}

# =============================================================================
# Internet Gateway (AC3 - Task 3)
# =============================================================================

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id  # Task 3.2 - Attach to VPC

  tags = {
    Name = "${var.project_name}-igw"  # Task 3.3
  }
}
