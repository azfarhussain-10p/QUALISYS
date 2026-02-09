# Azure Virtual Network
# QUALISYS Azure Infrastructure — mirrors AWS VPC configuration
# VNet 10.0.0.0/16 with 6 subnets across availability zones

# =============================================================================
# Virtual Network
# =============================================================================

resource "azurerm_virtual_network" "main" {
  name                = "${var.project_name}-${var.environment}-vnet"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.address_space

  tags = var.tags
}

# =============================================================================
# Subnets
# =============================================================================

# Public subnet (for Application Gateway / Load Balancer)
resource "azurerm_subnet" "public" {
  name                 = "${var.project_name}-public"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.public_subnet_cidr]
}

# AKS subnet (private — for Kubernetes nodes)
resource "azurerm_subnet" "aks" {
  name                 = "${var.project_name}-aks"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.aks_subnet_cidr]
}

# PostgreSQL subnet (delegated to PostgreSQL Flexible Server)
resource "azurerm_subnet" "postgresql" {
  name                 = "${var.project_name}-postgresql"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.postgresql_subnet_cidr]

  delegation {
    name = "postgresql-delegation"

    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# Redis subnet
resource "azurerm_subnet" "redis" {
  name                 = "${var.project_name}-redis"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.redis_subnet_cidr]
}

# Application Gateway subnet
resource "azurerm_subnet" "appgw" {
  name                 = "${var.project_name}-appgw"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.appgw_subnet_cidr]
}

# =============================================================================
# Network Security Groups
# =============================================================================

resource "azurerm_network_security_group" "aks" {
  name                = "${var.project_name}-${var.environment}-aks-nsg"
  location            = var.location
  resource_group_name = var.resource_group_name

  # Allow inbound from Application Gateway to AKS
  security_rule {
    name                       = "AllowAppGateway"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["80", "443"]
    source_address_prefix      = var.appgw_subnet_cidr
    destination_address_prefix = var.aks_subnet_cidr
  }

  # Allow inbound within VNet
  security_rule {
    name                       = "AllowVNetInbound"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
  }

  tags = var.tags
}

resource "azurerm_network_security_group" "postgresql" {
  name                = "${var.project_name}-${var.environment}-postgresql-nsg"
  location            = var.location
  resource_group_name = var.resource_group_name

  # Allow PostgreSQL from AKS subnet
  security_rule {
    name                       = "AllowPostgreSQLFromAKS"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "5432"
    source_address_prefix      = var.aks_subnet_cidr
    destination_address_prefix = var.postgresql_subnet_cidr
  }

  tags = var.tags
}

resource "azurerm_network_security_group" "redis" {
  name                = "${var.project_name}-${var.environment}-redis-nsg"
  location            = var.location
  resource_group_name = var.resource_group_name

  # Allow Redis from AKS subnet
  security_rule {
    name                       = "AllowRedisFromAKS"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "6380"
    source_address_prefix      = var.aks_subnet_cidr
    destination_address_prefix = var.redis_subnet_cidr
  }

  tags = var.tags
}

# =============================================================================
# NSG Associations
# =============================================================================

resource "azurerm_subnet_network_security_group_association" "aks" {
  subnet_id                 = azurerm_subnet.aks.id
  network_security_group_id = azurerm_network_security_group.aks.id
}

resource "azurerm_subnet_network_security_group_association" "postgresql" {
  subnet_id                 = azurerm_subnet.postgresql.id
  network_security_group_id = azurerm_network_security_group.postgresql.id
}

resource "azurerm_subnet_network_security_group_association" "redis" {
  subnet_id                 = azurerm_subnet.redis.id
  network_security_group_id = azurerm_network_security_group.redis.id
}

# =============================================================================
# NAT Gateway (for private subnet outbound internet access)
# =============================================================================

resource "azurerm_public_ip" "nat" {
  name                = "${var.project_name}-${var.environment}-nat-pip"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = var.tags
}

resource "azurerm_nat_gateway" "main" {
  name                    = "${var.project_name}-${var.environment}-natgw"
  location                = var.location
  resource_group_name     = var.resource_group_name
  sku_name                = "Standard"
  idle_timeout_in_minutes = 10

  tags = var.tags
}

resource "azurerm_nat_gateway_public_ip_association" "main" {
  nat_gateway_id       = azurerm_nat_gateway.main.id
  public_ip_address_id = azurerm_public_ip.nat.id
}

resource "azurerm_subnet_nat_gateway_association" "aks" {
  subnet_id      = azurerm_subnet.aks.id
  nat_gateway_id = azurerm_nat_gateway.main.id
}

# =============================================================================
# Private DNS Zone for PostgreSQL
# =============================================================================

resource "azurerm_private_dns_zone" "postgresql" {
  name                = "${var.project_name}-${var.environment}.postgres.database.azure.com"
  resource_group_name = var.resource_group_name

  tags = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "${var.project_name}-postgresql-dns-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = azurerm_virtual_network.main.id
}
