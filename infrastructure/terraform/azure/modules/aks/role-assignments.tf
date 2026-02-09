# AKS Role Assignments
# Grant AKS cluster identity necessary permissions

# Allow AKS to manage the subnet (for Azure CNI)
resource "azurerm_role_assignment" "aks_network_contributor" {
  scope                = var.resource_group_id
  role_definition_name = "Network Contributor"
  principal_id         = azurerm_kubernetes_cluster.main.identity[0].principal_id
}
