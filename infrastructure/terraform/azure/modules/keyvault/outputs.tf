output "key_vault_id" {
  description = "ID of the Key Vault"
  value       = azurerm_key_vault.main.id
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = azurerm_key_vault.main.vault_uri
}

output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = azurerm_key_vault.main.name
}

output "jwt_secret_id" {
  description = "Key Vault secret ID for JWT signing key"
  value       = azurerm_key_vault_secret.jwt_signing_key.id
}

output "openai_secret_id" {
  description = "Key Vault secret ID for OpenAI API key"
  value       = azurerm_key_vault_secret.llm_openai.id
}

output "anthropic_secret_id" {
  description = "Key Vault secret ID for Anthropic API key"
  value       = azurerm_key_vault_secret.llm_anthropic.id
}

output "oauth_google_client_id_secret_id" {
  description = "Key Vault secret ID for Google OAuth client ID"
  value       = azurerm_key_vault_secret.oauth_google_client_id.id
}

output "sendgrid_secret_id" {
  description = "Key Vault secret ID for SendGrid API key"
  value       = azurerm_key_vault_secret.email_sendgrid.id
}
