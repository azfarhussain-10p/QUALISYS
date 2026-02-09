# Azure Kubernetes Service (AKS)
# QUALISYS Azure Infrastructure — mirrors AWS EKS configuration
# AKS cluster with system + user node pools, Workload Identity, Azure CNI

# =============================================================================
# AKS Cluster
# =============================================================================

resource "azurerm_kubernetes_cluster" "main" {
  name                = "${var.project_name}-${var.environment}-aks"
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = "${var.project_name}-${var.environment}"
  kubernetes_version  = var.kubernetes_version

  # System node pool (general workloads)
  default_node_pool {
    name                = "general"
    vm_size             = var.general_node_vm_size
    min_count           = var.general_node_min_count
    max_count           = var.general_node_max_count
    enable_auto_scaling = true
    vnet_subnet_id      = var.vnet_subnet_id
    os_disk_size_gb     = 50
    max_pods            = 110

    node_labels = {
      "node-type" = "general"
    }

    tags = var.tags
  }

  # Managed identity for the cluster
  identity {
    type = "SystemAssigned"
  }

  # Azure CNI networking
  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"
    service_cidr      = "172.16.0.0/16"
    dns_service_ip    = "172.16.0.10"
    load_balancer_sku = "standard"
    outbound_type     = "userAssignedNATGateway"
  }

  # Workload Identity (Azure equivalent of AWS IRSA)
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  # Azure AD RBAC
  azure_active_directory_role_based_access_control {
    managed                = true
    azure_rbac_enabled     = true
  }

  # Monitoring
  oms_agent {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }

  # Key management
  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  # API server access (private cluster for production)
  api_server_access_profile {
    authorized_ip_ranges = var.environment == "production" ? var.authorized_ip_ranges : null
  }

  tags = var.tags
}

# =============================================================================
# Playwright Node Pool (user pool with taint)
# =============================================================================

resource "azurerm_kubernetes_cluster_node_pool" "playwright" {
  name                  = "playwright"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = var.playwright_node_vm_size
  min_count             = var.playwright_node_min_count
  max_count             = var.playwright_node_max_count
  enable_auto_scaling   = true
  vnet_subnet_id        = var.vnet_subnet_id
  os_disk_size_gb       = 100
  max_pods              = 110
  priority              = var.playwright_use_spot ? "Spot" : "Regular"
  eviction_policy       = var.playwright_use_spot ? "Delete" : null
  spot_max_price        = var.playwright_use_spot ? -1 : null

  node_labels = {
    "node-type" = "playwright"
  }

  node_taints = [
    "workload=playwright:NoSchedule"
  ]

  tags = var.tags
}
