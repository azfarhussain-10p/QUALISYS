# Azure Key Vault
# QUALISYS Azure Infrastructure — mirrors AWS Secrets Manager configuration
# Stores 8 secret categories matching AWS: DB, Redis, JWT, LLM (OpenAI, Anthropic), OAuth, Email

# =============================================================================
# Key Vault
# =============================================================================

resource "azurerm_key_vault" "main" {
  name                = "${var.project_name}-${var.environment}-kv"
  location            = var.location
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id
  sku_name            = "standard"

  # Soft delete (required, default 90 days)
  soft_delete_retention_days = var.recovery_days
  purge_protection_enabled   = var.environment == "production"

  # RBAC authorization (preferred over access policies)
  enable_rbac_authorization = true

  # Network rules
  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }

  tags = var.tags
}

# =============================================================================
# Application Secrets — Placeholders
# Actual values set manually after terraform apply (same pattern as AWS).
# lifecycle.ignore_changes prevents Terraform from overwriting manual updates.
# =============================================================================

# JWT Signing Secret (256-bit random)
resource "random_password" "jwt_signing_key" {
  length  = 64
  special = false
}

resource "azurerm_key_vault_secret" "jwt_signing_key" {
  name         = "jwt-signing-key"
  value        = random_password.jwt_signing_key.result
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(var.tags, { Category = "jwt" })
}

# LLM API Keys — Placeholders
resource "azurerm_key_vault_secret" "llm_openai" {
  name         = "llm-openai-api-key"
  value        = "REPLACE_WITH_ACTUAL_OPENAI_API_KEY"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(var.tags, { Category = "llm" })

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "llm_anthropic" {
  name         = "llm-anthropic-api-key"
  value        = "REPLACE_WITH_ACTUAL_ANTHROPIC_API_KEY"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(var.tags, { Category = "llm" })

  lifecycle {
    ignore_changes = [value]
  }
}

# OAuth Credentials — Placeholders
resource "azurerm_key_vault_secret" "oauth_google_client_id" {
  name         = "oauth-google-client-id"
  value        = "REPLACE_WITH_GOOGLE_CLIENT_ID"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(var.tags, { Category = "oauth" })

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "oauth_google_client_secret" {
  name         = "oauth-google-client-secret"
  value        = "REPLACE_WITH_GOOGLE_CLIENT_SECRET"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(var.tags, { Category = "oauth" })

  lifecycle {
    ignore_changes = [value]
  }
}

# Email Service — Placeholder
resource "azurerm_key_vault_secret" "email_sendgrid" {
  name         = "email-sendgrid-api-key"
  value        = "REPLACE_WITH_SENDGRID_API_KEY"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(var.tags, { Category = "email" })

  lifecycle {
    ignore_changes = [value]
  }
}
