# Story 0.22: Third-Party Service Accounts & API Keys

Status: ready-for-dev

## Story

As a **DevOps Engineer**,
I want **to provision all third-party service accounts and API keys**,
so that **Epic 2-5 integrations can be implemented without delays**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | OpenAI API account created, API key generated and stored in secret manager | Secret exists in AWS Secrets Manager |
| AC2 | Anthropic API account created, API key generated and stored | Secret exists in AWS Secrets Manager |
| AC3 | Google OAuth client ID/secret created for SSO (Epic 1) | OAuth credentials stored in Secrets Manager |
| AC4 | SendGrid or Postmark account created for transactional emails (Epic 1) | Email API key stored in Secrets Manager |
| AC5 | Jira integration account created (Epic 5, can defer) | Jira API token stored or documented for later |
| AC6 | Slack webhook configured for notifications (Epic 5, can defer) | Webhook URL stored in Secrets Manager |
| AC7 | GitHub App created for repository integration (Epic 3, can defer) | GitHub App credentials stored in Secrets Manager |
| AC8 | All API keys documented in secret manager with purpose and expiration | Secrets have description and tags |
| AC9 | API key rotation schedule defined (quarterly for LLM keys) | Rotation schedule documented |
| AC10 | Billing alerts configured for LLM APIs | OpenAI/Anthropic billing alerts set |
| AC11 | Rate limits and quotas documented | Documentation includes API limits |
| AC12 | ExternalSecrets configuration for Kubernetes access | ExternalSecrets syncs secrets to K8s |

## Tasks / Subtasks

- [ ] **Task 1: LLM Provider Accounts** (AC: 1, 2, 10)
  - [ ] 1.1 Create OpenAI organization account
  - [ ] 1.2 Generate OpenAI API key with usage limits
  - [ ] 1.3 Configure OpenAI billing alerts ($50, $100, $200)
  - [ ] 1.4 Store OpenAI API key in Secrets Manager
  - [ ] 1.5 Create Anthropic account
  - [ ] 1.6 Generate Anthropic API key
  - [ ] 1.7 Configure Anthropic billing alerts
  - [ ] 1.8 Store Anthropic API key in Secrets Manager

- [ ] **Task 2: Authentication Provider** (AC: 3)
  - [ ] 2.1 Create Google Cloud project for OAuth
  - [ ] 2.2 Configure OAuth consent screen
  - [ ] 2.3 Create OAuth 2.0 client credentials
  - [ ] 2.4 Add authorized redirect URIs
  - [ ] 2.5 Store client ID and secret in Secrets Manager

- [ ] **Task 3: Email Service** (AC: 4)
  - [ ] 3.1 Create SendGrid account (or Postmark)
  - [ ] 3.2 Verify sender domain
  - [ ] 3.3 Generate API key with appropriate permissions
  - [ ] 3.4 Configure email templates (optional)
  - [ ] 3.5 Store API key in Secrets Manager

- [ ] **Task 4: Integration Services** (AC: 5, 6, 7)
  - [ ] 4.1 Create Jira integration credentials (defer if not ready)
  - [ ] 4.2 Create Slack App and webhook URL
  - [ ] 4.3 Create GitHub App for repository integration
  - [ ] 4.4 Store all credentials in Secrets Manager

- [ ] **Task 5: Documentation and Security** (AC: 8, 9, 11)
  - [ ] 5.1 Document all secrets with purpose in Secrets Manager
  - [ ] 5.2 Add expiration tags to secrets
  - [ ] 5.3 Create API key rotation schedule
  - [ ] 5.4 Document rate limits and quotas
  - [ ] 5.5 Create credentials inventory spreadsheet

- [ ] **Task 6: Kubernetes Integration** (AC: 12)
  - [ ] 6.1 Configure ExternalSecrets Operator (if not already)
  - [ ] 6.2 Create ExternalSecret resources for each secret
  - [ ] 6.3 Verify secrets sync to Kubernetes namespaces
  - [ ] 6.4 Document secret access patterns

## Dev Notes

### Architecture Alignment

This story provisions integration credentials per architecture requirements:

- **Epic 2 (AI Agents)**: OpenAI/Anthropic API keys for LangChain
- **Epic 1 (Authentication)**: Google OAuth for SSO
- **Epic 1 (Notifications)**: SendGrid/Postmark for email
- **Epic 3 (GitHub Integration)**: GitHub App for PR integration
- **Epic 5 (Integrations)**: Jira, Slack for third-party integration

### Technical Constraints

- **Secret Storage**: AWS Secrets Manager (not environment variables)
- **Account Type**: Organizational accounts (not personal)
- **Billing**: Alerts configured to prevent runaway costs
- **Rotation**: Quarterly rotation for LLM API keys

### AWS Secrets Manager Structure

```
/qualisys/
├── production/
│   ├── llm/
│   │   ├── openai-api-key
│   │   └── anthropic-api-key
│   ├── auth/
│   │   ├── google-oauth-client-id
│   │   ├── google-oauth-client-secret
│   │   └── jwt-signing-secret
│   ├── email/
│   │   └── sendgrid-api-key
│   └── integrations/
│       ├── github-app-private-key
│       ├── github-app-id
│       ├── jira-api-token
│       └── slack-webhook-url
└── staging/
    └── (same structure)
```

### Terraform Secrets Configuration

```hcl
# modules/secrets/main.tf

# OpenAI API Key
resource "aws_secretsmanager_secret" "openai_api_key" {
  name        = "/qualisys/${var.environment}/llm/openai-api-key"
  description = "OpenAI API key for LangChain AI agents (Epic 2)"

  tags = {
    Environment = var.environment
    Service     = "ai-agents"
    Epic        = "2"
    RotationSchedule = "quarterly"
  }
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key  # Passed from secure source
}

# Anthropic API Key
resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "/qualisys/${var.environment}/llm/anthropic-api-key"
  description = "Anthropic API key for Claude AI agents (Epic 2)"

  tags = {
    Environment = var.environment
    Service     = "ai-agents"
    Epic        = "2"
    RotationSchedule = "quarterly"
  }
}

# Google OAuth Credentials
resource "aws_secretsmanager_secret" "google_oauth" {
  name        = "/qualisys/${var.environment}/auth/google-oauth"
  description = "Google OAuth client credentials for SSO (Epic 1)"

  tags = {
    Environment = var.environment
    Service     = "authentication"
    Epic        = "1"
  }
}

resource "aws_secretsmanager_secret_version" "google_oauth" {
  secret_id = aws_secretsmanager_secret.google_oauth.id
  secret_string = jsonencode({
    client_id     = var.google_oauth_client_id
    client_secret = var.google_oauth_client_secret
  })
}

# SendGrid API Key
resource "aws_secretsmanager_secret" "sendgrid_api_key" {
  name        = "/qualisys/${var.environment}/email/sendgrid-api-key"
  description = "SendGrid API key for transactional emails (Epic 1)"

  tags = {
    Environment = var.environment
    Service     = "email"
    Epic        = "1"
  }
}

# GitHub App Credentials
resource "aws_secretsmanager_secret" "github_app" {
  name        = "/qualisys/${var.environment}/integrations/github-app"
  description = "GitHub App credentials for repository integration (Epic 3)"

  tags = {
    Environment = var.environment
    Service     = "github-integration"
    Epic        = "3"
  }
}

resource "aws_secretsmanager_secret_version" "github_app" {
  secret_id = aws_secretsmanager_secret.github_app.id
  secret_string = jsonencode({
    app_id         = var.github_app_id
    client_id      = var.github_app_client_id
    client_secret  = var.github_app_client_secret
    private_key    = var.github_app_private_key
    webhook_secret = var.github_app_webhook_secret
  })
}

# Slack Webhook URL
resource "aws_secretsmanager_secret" "slack_webhook" {
  name        = "/qualisys/${var.environment}/integrations/slack-webhook"
  description = "Slack webhook URL for notifications (Epic 5)"

  tags = {
    Environment = var.environment
    Service     = "slack-integration"
    Epic        = "5"
  }
}

# Jira API Token (can be provisioned later)
resource "aws_secretsmanager_secret" "jira_api_token" {
  name        = "/qualisys/${var.environment}/integrations/jira-api-token"
  description = "Jira API token for issue tracking integration (Epic 5)"

  tags = {
    Environment = var.environment
    Service     = "jira-integration"
    Epic        = "5"
    Status      = "pending-provisioning"
  }
}
```

### ExternalSecrets Configuration

```yaml
# k8s/secrets/external-secrets.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: production
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa

---
# OpenAI API Key
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: openai-api-key
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: openai-api-key
    creationPolicy: Owner
  data:
    - secretKey: api-key
      remoteRef:
        key: /qualisys/production/llm/openai-api-key

---
# Anthropic API Key
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: anthropic-api-key
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: anthropic-api-key
    creationPolicy: Owner
  data:
    - secretKey: api-key
      remoteRef:
        key: /qualisys/production/llm/anthropic-api-key

---
# Google OAuth
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: google-oauth
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: google-oauth
    creationPolicy: Owner
  dataFrom:
    - extract:
        key: /qualisys/production/auth/google-oauth

---
# SendGrid API Key
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: sendgrid-api-key
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: sendgrid-api-key
    creationPolicy: Owner
  data:
    - secretKey: api-key
      remoteRef:
        key: /qualisys/production/email/sendgrid-api-key

---
# GitHub App
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: github-app
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: github-app
    creationPolicy: Owner
  dataFrom:
    - extract:
        key: /qualisys/production/integrations/github-app
```

### OpenAI Account Setup

1. **Create Organization Account**
   - Go to https://platform.openai.com
   - Sign up with company email (not personal)
   - Create organization: "QUALISYS"

2. **Generate API Key**
   - Navigate to API Keys section
   - Create new secret key
   - Name: `qualisys-production`
   - Copy key immediately (shown once)

3. **Configure Billing Alerts**
   - Go to Organization → Billing
   - Set usage limits:
     - Soft limit: $50 (warning)
     - Hard limit: $200 (stop requests)
   - Enable email alerts

4. **Rate Limits (GPT-4)**
   - Requests per minute: 10,000
   - Tokens per minute: 300,000
   - Document in API limits doc

### Anthropic Account Setup

1. **Create Account**
   - Go to https://console.anthropic.com
   - Sign up with company email
   - Complete organization verification

2. **Generate API Key**
   - Navigate to API Keys
   - Create key: `qualisys-production`
   - Copy key immediately

3. **Configure Billing**
   - Set up payment method
   - Configure usage alerts
   - Document rate limits

### Google OAuth Setup

1. **Create Google Cloud Project**
   - Go to https://console.cloud.google.com
   - Create project: "QUALISYS Production"
   - Enable Google+ API

2. **Configure OAuth Consent Screen**
   - User type: External
   - App name: QUALISYS
   - Support email: support@qualisys.io
   - Authorized domains: qualisys.io

3. **Create OAuth 2.0 Credentials**
   - Application type: Web application
   - Name: QUALISYS Web App
   - Authorized redirect URIs:
     - `https://app.qualisys.io/api/auth/callback/google`
     - `https://staging.qualisys.io/api/auth/callback/google`
     - `http://localhost:3000/api/auth/callback/google` (dev)

### SendGrid Setup

1. **Create Account**
   - Go to https://sendgrid.com
   - Sign up for free tier (100 emails/day)
   - Upgrade to Essentials ($19.95/mo) for production

2. **Domain Verification**
   - Add sender domain: qualisys.io
   - Add DNS records (CNAME, TXT)
   - Verify domain

3. **Generate API Key**
   - Name: `qualisys-production`
   - Permissions: Mail Send (Full Access)
   - Copy and store in Secrets Manager

### GitHub App Setup

1. **Create GitHub App**
   - Go to GitHub → Settings → Developer Settings → GitHub Apps
   - New GitHub App
   - Name: QUALISYS Integration
   - Homepage URL: https://qualisys.io
   - Webhook URL: https://api.qualisys.io/webhooks/github

2. **Permissions**
   - Repository permissions:
     - Contents: Read
     - Pull requests: Read & Write
     - Commit statuses: Read & Write
     - Checks: Read & Write
   - Organization permissions:
     - Members: Read

3. **Generate Private Key**
   - Download .pem file
   - Store in Secrets Manager

### API Key Rotation Schedule

| Service | Rotation Frequency | Next Rotation | Responsible |
|---------|-------------------|---------------|-------------|
| OpenAI | Quarterly | 2026-04-01 | DevOps Lead |
| Anthropic | Quarterly | 2026-04-01 | DevOps Lead |
| Google OAuth | Yearly | 2027-01-01 | DevOps Lead |
| SendGrid | Yearly | 2027-01-01 | DevOps Lead |
| GitHub App | Yearly | 2027-01-01 | DevOps Lead |
| Slack Webhook | On compromise | N/A | DevOps Lead |
| Jira Token | Yearly | 2027-01-01 | DevOps Lead |

### Rate Limits and Quotas

| Service | Rate Limit | Monthly Quota | Cost Control |
|---------|------------|---------------|--------------|
| **OpenAI GPT-4** | 10K RPM, 300K TPM | $200 hard limit | Billing alerts |
| **Anthropic Claude** | 4K RPM | $200 budget | Billing alerts |
| **SendGrid** | 100/day (free), 100K/mo (paid) | $19.95/mo | Plan limit |
| **Google OAuth** | Unlimited | Free | N/A |
| **GitHub App** | 5K/hr per installation | Free | N/A |

### Project Structure Notes

```
/
├── terraform/
│   └── modules/
│       └── secrets/
│           ├── main.tf           # Secret definitions
│           ├── variables.tf      # Input variables
│           └── outputs.tf        # Output values
├── k8s/
│   └── secrets/
│       └── external-secrets.yaml # ExternalSecret resources
└── docs/
    └── secrets/
        ├── README.md             # Secrets documentation
        ├── rotation-schedule.md  # Rotation procedures
        └── rate-limits.md        # API limits documentation
```

### Dependencies

- **Story 0.7** (Secret Management) - REQUIRED: Secrets Manager infrastructure
- **Story 0.1** (IAM Setup) - REQUIRED: IAM roles for secret access
- Outputs used by:
  - **Epic 1**: Google OAuth, SendGrid for authentication and email
  - **Epic 2**: OpenAI/Anthropic for AI agents
  - **Epic 3**: GitHub App for PR integration
  - **Epic 5**: Jira, Slack for third-party integrations

### Security Considerations

1. **Threat: Key exposure** → Store only in Secrets Manager, never in code
2. **Threat: Runaway costs** → Billing alerts and hard limits
3. **Threat: Stale keys** → Quarterly rotation schedule
4. **Threat: Over-permissioned keys** → Least privilege for each service
5. **Threat: Single point of failure** → Document recovery procedures

### Deferrable Items

These can be provisioned later if not immediately needed:

- **Jira Integration** (AC5) - Can defer to Epic 5 sprint
- **Slack Webhook** (AC6) - Can defer until notifications needed
- **GitHub App** (AC7) - Can defer to Epic 3 sprint

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Third-Party-Dependencies]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.22]
- [Source: docs/architecture.md#Integration-Architecture]
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Anthropic API Documentation](https://docs.anthropic.com)
- [SendGrid API Documentation](https://docs.sendgrid.com)
- [GitHub Apps Documentation](https://docs.github.com/en/apps)

## Dev Agent Record

### Context Reference

- [docs/stories/0-22-third-party-service-accounts-api-keys.context.xml](./0-22-third-party-service-accounts-api-keys.context.xml)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

### File List

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-24 | SM Agent (Bob) | Story drafted from Epic 0 tech spec and epic file |
