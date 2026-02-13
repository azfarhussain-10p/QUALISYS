# QUALISYS Third-Party Service Accounts & API Keys

Story: 0-22 Third-Party Service Accounts & API Keys

## Credentials Inventory

| Service | Category | Secret Path (AWS) | Key Vault Name (Azure) | Epic | Status |
|---------|----------|-------------------|------------------------|------|--------|
| **OpenAI** | LLM | `qualisys/llm/openai` | `llm-openai-api-key` | 2 | Placeholder |
| **Anthropic** | LLM | `qualisys/llm/anthropic` | `llm-anthropic-api-key` | 2 | Placeholder |
| **Google OAuth** | Auth | `qualisys/oauth/google` | `oauth-google-client-*` | 1 | Placeholder |
| **SendGrid** | Email | `qualisys/email/sendgrid` | `email-sendgrid-api-key` | 1 | Placeholder |
| **GitHub App** | Integration | `qualisys/integrations/github-app` | `integrations-github-app` | 3 | Placeholder |
| **Jira** | Integration | `qualisys/integrations/jira` | `integrations-jira-api-token` | 5 | Deferred |
| **Slack** | Integration | `qualisys/integrations/slack-webhook` | `integrations-slack-webhook` | 5 | Deferred |
| **JWT** | Auth | `qualisys/jwt/signing-key` | `jwt-signing-key` | 1 | Auto-generated |

> **Placeholder** = Terraform resource created with dummy value. Replace with real key after provisioning the service account.
> **Deferred** = Can be provisioned when the consuming Epic starts.

## Account Provisioning Guide

### 1. OpenAI (Epic 2 — AI Agents)

1. Create organization account at https://platform.openai.com
2. Sign up with **company email** (not personal)
3. Organization name: `QUALISYS`
4. Generate API key → Name: `qualisys-production`
5. Configure billing:
   - Soft limit: **$50** (email warning)
   - Hard limit: **$200** (stop requests)
6. Store key:
   ```bash
   # AWS
   aws secretsmanager put-secret-value \
     --secret-id qualisys/llm/openai \
     --secret-string '{"api_key":"sk-..."}'

   # Azure
   az keyvault secret set \
     --vault-name qualisys-secrets \
     --name llm-openai-api-key \
     --value "sk-..."
   ```

### 2. Anthropic (Epic 2 — AI Agents)

1. Create account at https://console.anthropic.com
2. Sign up with **company email**
3. Complete organization verification
4. Generate API key → Name: `qualisys-production`
5. Configure billing alerts: **$200 budget**
6. Store key using same pattern as OpenAI

### 3. Google OAuth (Epic 1 — Authentication)

1. Create Google Cloud project: `QUALISYS Production`
2. Enable **Google+ API** and **People API**
3. Configure OAuth consent screen:
   - User type: External
   - App name: QUALISYS
   - Support email: support@qualisys.io
4. Create OAuth 2.0 credentials:
   - Type: Web application
   - Name: `QUALISYS Web App`
   - Redirect URIs:
     - `https://app.qualisys.io/api/auth/callback/google`
     - `https://staging.qualisys.io/api/auth/callback/google`
     - `http://localhost:3000/api/auth/callback/google` (dev)
5. Store credentials:
   ```bash
   # AWS
   aws secretsmanager put-secret-value \
     --secret-id qualisys/oauth/google \
     --secret-string '{"client_id":"...","client_secret":"..."}'

   # Azure
   az keyvault secret set --vault-name qualisys-secrets \
     --name oauth-google-client-id --value "..."
   az keyvault secret set --vault-name qualisys-secrets \
     --name oauth-google-client-secret --value "..."
   ```

### 4. SendGrid (Epic 1 — Transactional Email)

1. Create account at https://sendgrid.com
2. Start with **free tier** (100 emails/day), upgrade to Essentials for production
3. Verify sender domain: `qualisys.io` (add DNS CNAME + TXT records)
4. Generate API key → Name: `qualisys-production`, Permissions: **Mail Send (Full Access)**
5. Store key using same pattern

### 5. GitHub App (Epic 3 — PR Integration)

1. GitHub → Settings → Developer Settings → GitHub Apps → New
2. Configure:
   - Name: `QUALISYS Integration`
   - Homepage: `https://qualisys.io`
   - Webhook URL: `https://api.qualisys.io/webhooks/github`
3. Permissions:
   - Repository: Contents (Read), Pull Requests (R+W), Commit Statuses (R+W), Checks (R+W)
   - Organization: Members (Read)
4. Generate private key (.pem)
5. Store credentials:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id qualisys/integrations/github-app \
     --secret-string '{"app_id":"...","client_id":"...","client_secret":"...","private_key":"-----BEGIN RSA PRIVATE KEY-----\n...","webhook_secret":"..."}'
   ```

### 6. Jira (Epic 5 — Deferred)

1. Create Jira service account with API token
2. Store: `qualisys/integrations/jira`

### 7. Slack (Epic 5 — Deferred)

1. Create Slack App → Enable Incoming Webhooks
2. Store: `qualisys/integrations/slack-webhook`

## Rotation Schedule

| Service | Frequency | Next Rotation | Owner | Procedure |
|---------|-----------|---------------|-------|-----------|
| **OpenAI** | Quarterly | 2026-07-01 | DevOps Lead | Regenerate key in OpenAI dashboard, update secret store |
| **Anthropic** | Quarterly | 2026-07-01 | DevOps Lead | Regenerate key in Anthropic console, update secret store |
| **Google OAuth** | Yearly | 2027-01-01 | DevOps Lead | Rotate client secret in GCP console, update secret store |
| **SendGrid** | Yearly | 2027-01-01 | DevOps Lead | Regenerate API key in SendGrid, update secret store |
| **GitHub App** | Yearly | 2027-01-01 | DevOps Lead | Regenerate private key, update secret store |
| **Slack Webhook** | On compromise | N/A | DevOps Lead | Regenerate webhook URL in Slack App settings |
| **Jira Token** | Yearly | 2027-01-01 | DevOps Lead | Regenerate API token in Atlassian account |
| **JWT Signing Key** | N/A | Auto-rotated | Terraform | Managed by Terraform random_password |
| **Database** | 90 days | Auto-rotated | Lambda | AWS Secrets Manager rotation Lambda (Story 0-7) |

### Rotation Procedure

1. Generate new key in the service provider dashboard
2. Update secret store:
   ```bash
   # AWS
   aws secretsmanager put-secret-value --secret-id <path> --secret-string '<json>'

   # Azure
   az keyvault secret set --vault-name qualisys-secrets --name <name> --value '<value>'
   ```
3. ExternalSecrets syncs to K8s within 1 hour (refreshInterval: 1h)
4. Rolling restart pods to pick up new secret: `kubectl rollout restart deployment/<name> -n <ns>`
5. Verify application health after rotation
6. Update `NextRotation` tag on the secret

## Rate Limits & Quotas

| Service | Rate Limit | Monthly Quota | Cost Control |
|---------|------------|---------------|--------------|
| **OpenAI GPT-4** | 10,000 RPM / 300,000 TPM | $200 hard limit | Billing alerts at $50, $100, $200 |
| **Anthropic Claude** | 4,000 RPM | $200 budget | Billing alerts configured |
| **SendGrid** | 100/day (free) / 100K/mo (paid) | $19.95/mo (Essentials) | Plan limit |
| **Google OAuth** | Unlimited | Free | N/A |
| **GitHub API** | 5,000/hr per installation | Free | N/A |
| **Jira API** | 100/min per user | Free (Cloud) | N/A |
| **Slack Webhooks** | 1/sec per webhook | Free | Rate limiting |

### Cost Monitoring

- **OpenAI**: Configure billing alerts at https://platform.openai.com/account/billing
- **Anthropic**: Configure usage alerts at https://console.anthropic.com/settings/billing
- **SendGrid**: Monitor usage at https://app.sendgrid.com/statistics
- Application-level token budget monitoring is implemented in Epic 2 (Story 2-18)

## Kubernetes Secret Access

Secrets are synced from cloud secret stores to Kubernetes via ExternalSecrets Operator:

```
Cloud Secret Store                    Kubernetes
┌─────────────────┐                  ┌─────────────────┐
│ AWS Secrets Mgr  │  ExternalSecret  │ K8s Secret      │
│ or               │ ──────────────→  │ (namespace)     │
│ Azure Key Vault  │  refreshInterval │                 │
└─────────────────┘      1h          └─────────────────┘
```

### Accessing Secrets in Pods

```yaml
# Reference in deployment spec
env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: openai-api-key    # ExternalSecret target name
        key: api-key             # Key within the K8s Secret

  - name: GOOGLE_CLIENT_ID
    valueFrom:
      secretKeyRef:
        name: google-oauth
        key: client_id
```

### Verify Sync

```bash
# Check ExternalSecret status
kubectl get externalsecret -n production

# Check synced K8s secrets
kubectl get secret openai-api-key -n production -o jsonpath='{.data.api-key}' | base64 -d
```

## Infrastructure Files

| File | Purpose |
|------|---------|
| `infrastructure/terraform/aws/secrets/main.tf` | AWS Secrets Manager resources |
| `infrastructure/terraform/aws/secrets/iam.tf` | IAM policies for secret access |
| `infrastructure/terraform/aws/secrets/outputs.tf` | Secret ARN outputs |
| `infrastructure/terraform/azure/modules/secrets/main.tf` | Azure Key Vault resources |
| `infrastructure/terraform/azure/modules/secrets/variables.tf` | Azure module variables |
| `infrastructure/terraform/azure/modules/secrets/outputs.tf` | Azure module outputs |
| `infrastructure/kubernetes/secrets/cluster-secret-store-aws.yaml` | ClusterSecretStore for AWS |
| `infrastructure/kubernetes/secrets/cluster-secret-store-azure.yaml` | ClusterSecretStore for Azure |
| `infrastructure/kubernetes/secrets/external-secrets.yaml` | ExternalSecret resources |

## Security

- All secrets encrypted at rest (KMS on AWS, Key Vault encryption on Azure)
- Network-restricted Key Vault (Azure) — deny by default, allow Azure Services
- Category-based IAM policies — least privilege per service
- Audit logging via CloudTrail (AWS) / Activity Log (Azure)
- Unauthorized access alarm via EventBridge + CloudWatch (Story 0-7)
- Placeholder values (`REPLACE_WITH_*`) ensure no real secrets in source control
