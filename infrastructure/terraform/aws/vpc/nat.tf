# NAT Gateways and Elastic IPs
# Story: 0-2 VPC & Network Configuration
# AC: 4 - NAT Gateway in each AZ for private subnet internet access

# =============================================================================
# Elastic IPs for NAT Gateways (Task 4.1, 4.2)
# =============================================================================

resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat-eip-${var.availability_zones[count.index]}"
  }

  depends_on = [aws_internet_gateway.main]
}

# =============================================================================
# NAT Gateways - one per AZ for HA (Task 4.3, 4.4, 4.5)
# =============================================================================

resource "aws_nat_gateway" "main" {
  count = length(var.availability_zones)

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id  # NAT GW must be in public subnet

  tags = {
    Name = "${var.project_name}-nat-${var.availability_zones[count.index]}"
    AZ   = var.availability_zones[count.index]
  }

  depends_on = [aws_internet_gateway.main]
}
