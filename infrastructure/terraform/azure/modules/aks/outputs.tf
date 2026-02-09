output "cluster_name" {
  description = "Name of the AKS cluster"
  value       = azurerm_kubernetes_cluster.main.name
}

output "cluster_id" {
  description = "ID of the AKS cluster"
  value       = azurerm_kubernetes_cluster.main.id
}

output "cluster_endpoint" {
  description = "Endpoint for the AKS cluster API server"
  value       = azurerm_kubernetes_cluster.main.fqdn
}

output "cluster_ca_certificate" {
  description = "Base64 encoded CA certificate for the cluster"
  value       = azurerm_kubernetes_cluster.main.kube_config[0].cluster_ca_certificate
  sensitive   = true
}

output "kube_config_raw" {
  description = "Raw kubeconfig for the AKS cluster"
  value       = azurerm_kubernetes_cluster.main.kube_config_raw
  sensitive   = true
}

output "kubelet_identity_object_id" {
  description = "Object ID of the kubelet managed identity (for ACR pull)"
  value       = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
}

output "cluster_identity_principal_id" {
  description = "Principal ID of the cluster managed identity"
  value       = azurerm_kubernetes_cluster.main.identity[0].principal_id
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL for Workload Identity (Azure equivalent of IRSA)"
  value       = azurerm_kubernetes_cluster.main.oidc_issuer_url
}

output "node_resource_group" {
  description = "Auto-generated resource group for AKS node resources"
  value       = azurerm_kubernetes_cluster.main.node_resource_group
}
