# Azure AD & Managed Identities
# QUALISYS Azure Infrastructure — mirrors AWS IAM roles configuration
# Managed Identities for workload identity, role assignments

# =============================================================================
# Azure AD Groups (mirrors AWS IAM roles)
# =============================================================================

resource "azuread_group" "devops" {
  display_name     = "${var.project_name}-devops"
  description      = "DevOps administrators with full infrastructure access"
  security_enabled = true
}

resource "azuread_group" "developers" {
  display_name     = "${var.project_name}-developers"
  description      = "Developers with deploy access to dev/staging"
  security_enabled = true
}

resource "azuread_group" "cicd" {
  display_name     = "${var.project_name}-cicd"
  description      = "CI/CD service principals for automated deployments"
  security_enabled = true
}

# =============================================================================
# User-Assigned Managed Identities (for Workload Identity Federation)
# =============================================================================

# ExternalSecrets Operator identity (mirrors AWS IRSA for external-secrets)
resource "azurerm_user_assigned_identity" "external_secrets" {
  name                = "${var.project_name}-${var.environment}-external-secrets"
  resource_group_name = var.resource_group_name
  location            = var.location

  tags = var.tags
}

# Application workload identity (for app pods to access Key Vault)
resource "azurerm_user_assigned_identity" "app_workload" {
  name                = "${var.project_name}-${var.environment}-app-workload"
  resource_group_name = var.resource_group_name
  location            = var.location

  tags = var.tags
}

# =============================================================================
# Federated Identity Credentials (Workload Identity — Azure equivalent of IRSA)
# =============================================================================

resource "azurerm_federated_identity_credential" "external_secrets" {
  name                = "external-secrets-federated"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.external_secrets.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:external-secrets:external-secrets-sa"
}

resource "azurerm_federated_identity_credential" "app_workload_staging" {
  name                = "app-workload-staging"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.app_workload.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:staging:qualisys-api"
}

resource "azurerm_federated_identity_credential" "app_workload_production" {
  name                = "app-workload-production"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.app_workload.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:production:qualisys-api"
}

# =============================================================================
# Role Assignments — Key Vault Access
# =============================================================================

# ExternalSecrets operator gets Key Vault Secrets User role
resource "azurerm_role_assignment" "external_secrets_kv" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.external_secrets.principal_id
}

# App workload gets Key Vault Secrets User role
resource "azurerm_role_assignment" "app_workload_kv" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app_workload.principal_id
}

# =============================================================================
# Role Assignments — DevOps group gets Contributor on resource group
# =============================================================================

resource "azurerm_role_assignment" "devops_contributor" {
  scope                = var.resource_group_id
  role_definition_name = "Contributor"
  principal_id         = azuread_group.devops.object_id
}

# Developers get Reader + AKS Cluster User
resource "azurerm_role_assignment" "developers_reader" {
  scope                = var.resource_group_id
  role_definition_name = "Reader"
  principal_id         = azuread_group.developers.object_id
}

# =============================================================================
# Role Assignments — ACR Push for CI/CD
# =============================================================================

resource "azurerm_role_assignment" "cicd_acr_push" {
  scope                = var.acr_id
  role_definition_name = "AcrPush"
  principal_id         = azuread_group.cicd.object_id
}
