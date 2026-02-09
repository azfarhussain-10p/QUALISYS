# Route Tables and Associations
# Story: 0-2 VPC & Network Configuration
# AC: 5 - Route tables: public → IGW, private → NAT, database → no internet

# =============================================================================
# Public Route Table (Task 5.1)
# =============================================================================

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
    Type = "public"
  }
}

# =============================================================================
# Private Route Tables - one per AZ for AZ-local NAT (Task 5.2, 5.3)
# =============================================================================

resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = {
    Name = "${var.project_name}-private-rt-${var.availability_zones[count.index]}"
    Type = "private"
    AZ   = var.availability_zones[count.index]
  }
}

# =============================================================================
# Database Route Table - local only, NO internet (Task 5.4)
# =============================================================================

resource "aws_route_table" "database" {
  vpc_id = aws_vpc.main.id

  # No routes added — only implicit local route exists
  # Database subnets are isolated from the internet

  tags = {
    Name = "${var.project_name}-database-rt"
    Type = "database"
  }
}

# =============================================================================
# Route Table Associations (Task 5.5)
# =============================================================================

resource "aws_route_table_association" "public" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = length(var.private_subnet_cidrs)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table_association" "database" {
  count          = length(var.database_subnet_cidrs)
  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.database.id
}
