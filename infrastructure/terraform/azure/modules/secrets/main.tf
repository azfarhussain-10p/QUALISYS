# Azure Key Vault Secrets — Third-Party Service Accounts
# Story: 0-22 Third-Party Service Accounts & API Keys
# AC: 1-8 — All third-party secrets stored in Key Vault
# AC: 12  — ExternalSecrets integration via Workload Identity
#
# Note: AWS equivalent is infrastructure/terraform/aws/secrets/main.tf (Story 0-7)

# =============================================================================
# Key Vault for Application Secrets
# =============================================================================

resource "azurerm_key_vault" "secrets" {
  name                       = "${var.project_name}-secrets"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 30
  purge_protection_enabled   = true
  enable_rbac_authorization  = true

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = merge(var.tags, {
    Component = "secrets"
  })
}

data "azurerm_client_config" "current" {}

# =============================================================================
# RBAC — Terraform deployer as Key Vault Administrator
# =============================================================================

resource "azurerm_role_assignment" "deployer_kv_admin" {
  scope                = azurerm_key_vault.secrets.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

# =============================================================================
# LLM API Keys (AC1, AC2)
# =============================================================================

resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "llm-openai-api-key"
  value        = "REPLACE_WITH_ACTUAL_OPENAI_API_KEY"
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "text/plain"
  tags = {
    Description      = "OpenAI API key for LangChain AI agents (Epic 2)"
    Category         = "llm"
    Epic             = "2"
    RotationSchedule = "quarterly"
    NextRotation     = "2026-07-01"
    BillingAlert     = "200-usd-hard-limit"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "anthropic_api_key" {
  name         = "llm-anthropic-api-key"
  value        = "REPLACE_WITH_ACTUAL_ANTHROPIC_API_KEY"
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "text/plain"
  tags = {
    Description      = "Anthropic API key for Claude AI agents (Epic 2)"
    Category         = "llm"
    Epic             = "2"
    RotationSchedule = "quarterly"
    NextRotation     = "2026-07-01"
    BillingAlert     = "200-usd-budget"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

# =============================================================================
# Google OAuth Credentials (AC3)
# =============================================================================

resource "azurerm_key_vault_secret" "google_oauth_client_id" {
  name         = "oauth-google-client-id"
  value        = "REPLACE_WITH_GOOGLE_CLIENT_ID"
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "text/plain"
  tags = {
    Description      = "Google OAuth 2.0 client ID for SSO (Epic 1)"
    Category         = "oauth"
    Epic             = "1"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "google_oauth_client_secret" {
  name         = "oauth-google-client-secret"
  value        = "REPLACE_WITH_GOOGLE_CLIENT_SECRET"
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "text/plain"
  tags = {
    Description      = "Google OAuth 2.0 client secret for SSO (Epic 1)"
    Category         = "oauth"
    Epic             = "1"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

# =============================================================================
# Email Service — SendGrid (AC4)
# =============================================================================

resource "azurerm_key_vault_secret" "sendgrid_api_key" {
  name         = "email-sendgrid-api-key"
  value        = "REPLACE_WITH_SENDGRID_API_KEY"
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "text/plain"
  tags = {
    Description      = "SendGrid API key for transactional emails (Epic 1)"
    Category         = "email"
    Epic             = "1"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

# =============================================================================
# GitHub App Credentials (AC7)
# =============================================================================

resource "azurerm_key_vault_secret" "github_app" {
  name         = "integrations-github-app"
  value        = jsonencode({
    app_id         = "REPLACE_WITH_GITHUB_APP_ID"
    client_id      = "REPLACE_WITH_GITHUB_CLIENT_ID"
    client_secret  = "REPLACE_WITH_GITHUB_CLIENT_SECRET"
    private_key    = "REPLACE_WITH_GITHUB_PRIVATE_KEY_PEM"
    webhook_secret = "REPLACE_WITH_GITHUB_WEBHOOK_SECRET"
  })
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "application/json"
  tags = {
    Description      = "GitHub App credentials for repository integration (Epic 3)"
    Category         = "integrations"
    Epic             = "3"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

# =============================================================================
# Jira API Token (AC5 — can defer to Epic 5)
# =============================================================================

resource "azurerm_key_vault_secret" "jira_api_token" {
  name         = "integrations-jira-api-token"
  value        = jsonencode({
    email     = "REPLACE_WITH_JIRA_SERVICE_ACCOUNT_EMAIL"
    api_token = "REPLACE_WITH_JIRA_API_TOKEN"
    base_url  = "REPLACE_WITH_JIRA_BASE_URL"
  })
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "application/json"
  tags = {
    Description      = "Jira API token for issue tracking integration (Epic 5)"
    Category         = "integrations"
    Epic             = "5"
    RotationSchedule = "yearly"
    NextRotation     = "2027-01-01"
    Status           = "pending-provisioning"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

# =============================================================================
# Slack Webhook URL (AC6 — can defer to Epic 5)
# =============================================================================

resource "azurerm_key_vault_secret" "slack_webhook" {
  name         = "integrations-slack-webhook"
  value        = jsonencode({
    webhook_url = "REPLACE_WITH_SLACK_WEBHOOK_URL"
    channel     = "#qualisys-alerts"
  })
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "application/json"
  tags = {
    Description      = "Slack webhook URL for notifications (Epic 5)"
    Category         = "integrations"
    Epic             = "5"
    RotationSchedule = "on-compromise"
  }

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

# =============================================================================
# JWT Signing Key (auto-generated)
# =============================================================================

resource "random_password" "jwt_signing_key" {
  length  = 64
  special = false
}

resource "azurerm_key_vault_secret" "jwt_signing_key" {
  name         = "jwt-signing-key"
  value        = random_password.jwt_signing_key.result
  key_vault_id = azurerm_key_vault.secrets.id

  content_type = "text/plain"
  tags = {
    Description = "JWT signing secret (256-bit) for authentication token signing"
    Category    = "jwt"
  }

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

# =============================================================================
# RBAC — ExternalSecrets Operator (AC12)
# Workload Identity for K8s access to Key Vault secrets
# =============================================================================

resource "azurerm_user_assigned_identity" "external_secrets" {
  name                = "${var.project_name}-external-secrets"
  resource_group_name = var.resource_group_name
  location            = var.location

  tags = var.tags
}

resource "azurerm_federated_identity_credential" "external_secrets" {
  name                = "${var.project_name}-external-secrets"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.external_secrets.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:external-secrets:external-secrets-sa"
}

resource "azurerm_role_assignment" "external_secrets_kv_reader" {
  scope                = azurerm_key_vault.secrets.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.external_secrets.principal_id
}

# =============================================================================
# RBAC — Application pods (per-category access)
# =============================================================================

resource "azurerm_role_assignment" "app_kv_reader" {
  count                = var.app_identity_principal_id != "" ? 1 : 0
  scope                = azurerm_key_vault.secrets.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.app_identity_principal_id
}
