# Azure Key Vault Secrets — Outputs
# Story: 0-22 Third-Party Service Accounts & API Keys

output "key_vault_id" {
  description = "ID of the Key Vault"
  value       = azurerm_key_vault.secrets.id
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = azurerm_key_vault.secrets.vault_uri
}

output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = azurerm_key_vault.secrets.name
}

output "external_secrets_client_id" {
  description = "Client ID of the ExternalSecrets Workload Identity"
  value       = azurerm_user_assigned_identity.external_secrets.client_id
}

output "external_secrets_principal_id" {
  description = "Principal ID of the ExternalSecrets Workload Identity"
  value       = azurerm_user_assigned_identity.external_secrets.principal_id
}

# Individual secret IDs for reference
output "openai_secret_id" {
  description = "ID of the OpenAI API key secret"
  value       = azurerm_key_vault_secret.openai_api_key.id
}

output "anthropic_secret_id" {
  description = "ID of the Anthropic API key secret"
  value       = azurerm_key_vault_secret.anthropic_api_key.id
}

output "google_oauth_client_id_secret_id" {
  description = "ID of the Google OAuth client ID secret"
  value       = azurerm_key_vault_secret.google_oauth_client_id.id
}

output "sendgrid_secret_id" {
  description = "ID of the SendGrid API key secret"
  value       = azurerm_key_vault_secret.sendgrid_api_key.id
}

output "github_app_secret_id" {
  description = "ID of the GitHub App credentials secret"
  value       = azurerm_key_vault_secret.github_app.id
}

output "google_oauth_client_secret_secret_id" {
  description = "ID of the Google OAuth client secret secret"
  value       = azurerm_key_vault_secret.google_oauth_client_secret.id
}

output "jira_api_token_secret_id" {
  description = "ID of the Jira API token secret"
  value       = azurerm_key_vault_secret.jira_api_token.id
}

output "slack_webhook_secret_id" {
  description = "ID of the Slack webhook URL secret"
  value       = azurerm_key_vault_secret.slack_webhook.id
}

output "jwt_signing_key_secret_id" {
  description = "ID of the JWT signing key secret"
  value       = azurerm_key_vault_secret.jwt_signing_key.id
}
