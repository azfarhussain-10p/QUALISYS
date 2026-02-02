# Story 0.7: Secret Management

Status: ready-for-dev

## Story

As a **DevOps Engineer**,
I want to **configure a secret management system with rotation and audit logging**,
so that **we can securely store and access API keys, database passwords, and credentials across all environments**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | AWS Secrets Manager configured as primary secret store | `aws secretsmanager list-secrets` returns secrets |
| AC2 | Database connection string secret created and stored | `aws secretsmanager get-secret-value --secret-id qualisys/database/connection` succeeds |
| AC3 | Redis connection string secret created and stored | `aws secretsmanager get-secret-value --secret-id qualisys/redis/connection` succeeds |
| AC4 | JWT signing secret created (256-bit random) | Secret exists with 32+ character value |
| AC5 | LLM API keys stored: OpenAI API key, Anthropic API key | Both secrets exist in Secrets Manager |
| AC6 | OAuth credentials stored: Google OAuth client ID/secret | Secret exists with client_id and client_secret fields |
| AC7 | Email service API key stored (SendGrid/Postmark) | Secret exists for email service |
| AC8 | Kubernetes ExternalSecrets Operator installed and configured | `kubectl get pods -n external-secrets` shows operator running |
| AC9 | ExternalSecrets sync secrets from AWS to Kubernetes | `kubectl get externalsecrets` shows synced status |
| AC10 | Secret rotation configured: database password every 90 days | Rotation schedule configured in Secrets Manager |
| AC11 | Access audit logging enabled for all secrets | CloudTrail shows secretsmanager:GetSecretValue events |
| AC12 | IAM policies restrict secret access to specific roles | Only authorized roles can access secrets |

## Tasks / Subtasks

- [ ] **Task 1: Secrets Manager Setup** (AC: 1)
  - [ ] 1.1 Verify AWS Secrets Manager is available in target region
  - [ ] 1.2 Create KMS key for secret encryption (or use aws/secretsmanager default)
  - [ ] 1.3 Define secret naming convention: qualisys/{category}/{name}
  - [ ] 1.4 Document secret structure in infrastructure README

- [ ] **Task 2: Infrastructure Secrets Creation** (AC: 2, 3, 4)
  - [ ] 2.1 Create secret: qualisys/database/connection (from Story 0.4 output)
  - [ ] 2.2 Create secret: qualisys/redis/connection (from Story 0.5 output)
  - [ ] 2.3 Generate and store JWT signing secret (256-bit cryptographically random)
  - [ ] 2.4 Create secret: qualisys/jwt/signing-key
  - [ ] 2.5 Store secrets via Terraform with lifecycle ignore_changes on secret_string

- [ ] **Task 3: Third-Party API Keys** (AC: 5, 6, 7)
  - [ ] 3.1 Create secret: qualisys/llm/openai with API key
  - [ ] 3.2 Create secret: qualisys/llm/anthropic with API key
  - [ ] 3.3 Create secret: qualisys/oauth/google with client_id and client_secret
  - [ ] 3.4 Create secret: qualisys/email/sendgrid (or postmark) with API key
  - [ ] 3.5 Document API key rotation schedule and responsible party

- [ ] **Task 4: ExternalSecrets Operator Installation** (AC: 8, 9)
  - [ ] 4.1 Create external-secrets namespace in Kubernetes
  - [ ] 4.2 Install ExternalSecrets Operator via Helm
  - [ ] 4.3 Create ClusterSecretStore pointing to AWS Secrets Manager
  - [ ] 4.4 Configure IRSA (IAM Roles for Service Accounts) for operator
  - [ ] 4.5 Create ExternalSecret resources for each application secret
  - [ ] 4.6 Verify secrets synced to Kubernetes namespaces

- [ ] **Task 5: Secret Rotation Configuration** (AC: 10)
  - [ ] 5.1 Create Lambda function for database password rotation
  - [ ] 5.2 Configure rotation schedule: 90 days for database password
  - [ ] 5.3 Test rotation in dev environment
  - [ ] 5.4 Document rotation process and manual rotation procedure
  - [ ] 5.5 Configure rotation notifications (SNS topic)

- [ ] **Task 6: IAM and Audit Configuration** (AC: 11, 12)
  - [ ] 6.1 Create IAM policy: secrets-read-infra (database, redis, jwt)
  - [ ] 6.2 Create IAM policy: secrets-read-llm (openai, anthropic)
  - [ ] 6.3 Create IAM policy: secrets-read-integrations (oauth, email)
  - [ ] 6.4 Attach policies to appropriate IAM roles (app pods, CI/CD)
  - [ ] 6.5 Verify CloudTrail logging for Secrets Manager API calls
  - [ ] 6.6 Create CloudWatch alarm for unauthorized access attempts

- [ ] **Task 7: Validation & Documentation** (AC: All)
  - [ ] 7.1 Run all acceptance criteria verification commands
  - [ ] 7.2 Test secret retrieval from Kubernetes pod
  - [ ] 7.3 Verify ExternalSecrets sync on secret update
  - [ ] 7.4 Test rotation process end-to-end
  - [ ] 7.5 Document secret management process in README
  - [ ] 7.6 Create runbook for secret rotation and emergency rotation

## Dev Notes

### Architecture Alignment

This story implements the secret management foundation per the architecture document:

- **Centralized Secrets**: All credentials in AWS Secrets Manager (never in Git)
- **Kubernetes Integration**: ExternalSecrets Operator syncs to K8s secrets
- **Automatic Rotation**: Database passwords rotate every 90 days
- **Audit Trail**: CloudTrail logs all secret access for compliance

### Technical Constraints

- **No Secrets in Git**: All secrets managed via Secrets Manager
- **No Secrets in Docker Images**: Applications retrieve at runtime
- **Encryption**: All secrets encrypted with AWS KMS
- **Least Privilege**: Separate IAM policies per secret category
- **IRSA Required**: ExternalSecrets uses IAM Roles for Service Accounts

### Secret Naming Convention

```
qualisys/{category}/{name}

Categories:
- database    - Database connection strings
- redis       - Redis/cache connection strings
- jwt         - JWT signing keys
- llm         - LLM provider API keys (OpenAI, Anthropic)
- oauth       - OAuth provider credentials
- email       - Email service API keys
- integrations - Third-party integration credentials
```

### Secret Structure

| Secret ID | Fields | Consumers |
|-----------|--------|-----------|
| qualisys/database/connection | host, port, database, username, password | API pods |
| qualisys/redis/connection | primary_endpoint, reader_endpoint, port, auth_token | API pods |
| qualisys/jwt/signing-key | secret (256-bit) | API pods |
| qualisys/llm/openai | api_key | AI Agent pods |
| qualisys/llm/anthropic | api_key | AI Agent pods |
| qualisys/oauth/google | client_id, client_secret | API pods |
| qualisys/email/sendgrid | api_key | API pods |

### ExternalSecrets Configuration

```yaml
# ClusterSecretStore
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets

---
# ExternalSecret Example
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-credentials
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: database-credentials
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: qualisys/database/connection
        property: connection_string
```

### IAM Policies

**Infrastructure Secrets Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:qualisys/database/*",
        "arn:aws:secretsmanager:*:*:secret:qualisys/redis/*",
        "arn:aws:secretsmanager:*:*:secret:qualisys/jwt/*"
      ]
    }
  ]
}
```

### Rotation Schedule

| Secret | Rotation Period | Method |
|--------|-----------------|--------|
| Database password | 90 days | Lambda rotation function |
| Redis auth token | Manual | Coordinate with ElastiCache |
| JWT signing key | Annual | Manual with key versioning |
| LLM API keys | Quarterly | Manual (provider regeneration) |
| OAuth credentials | Annual | Manual (Google Cloud Console) |

### Project Structure Notes

```
infrastructure/
├── terraform/
│   ├── secrets/
│   │   ├── main.tf              # Secrets Manager secrets
│   │   ├── rotation.tf          # Lambda rotation configuration
│   │   ├── iam.tf               # Secret access IAM policies
│   │   ├── variables.tf         # Secret variables
│   │   └── outputs.tf           # Secret ARNs
│   └── ...
├── kubernetes/
│   ├── external-secrets/
│   │   ├── values.yaml          # Helm values for operator
│   │   ├── cluster-secret-store.yaml
│   │   └── external-secrets/    # ExternalSecret resources per namespace
│   └── ...
└── README.md                    # Secret management documentation
```

### Dependencies

- **Story 0.1** (Cloud Account & IAM Setup) - REQUIRED: IAM roles for IRSA
- **Story 0.3** (Kubernetes Cluster) - REQUIRED: OIDC provider for IRSA
- **Story 0.4** (PostgreSQL Database) - Provides database connection string
- **Story 0.5** (Redis) - Provides Redis connection string
- Outputs used by subsequent stories:
  - All Epic 1-6 stories: Application secrets access

### Security Considerations

From Red Team Analysis:

1. **Threat: Credential theft from Git** → Mitigated by Secrets Manager (AC1)
2. **Threat: Stale credentials** → Mitigated by rotation (AC10)
3. **Threat: Unauthorized access** → Mitigated by IAM policies (AC12)
4. **Threat: No audit trail** → Mitigated by CloudTrail logging (AC11)
5. **Threat: Secrets in container images** → Mitigated by runtime retrieval via ExternalSecrets

### Cost Estimate

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| Secrets Manager | 10 secrets | ~$4.00 |
| KMS Key | 1 CMK (optional) | ~$1.00 |
| Lambda (rotation) | 1 function, minimal invocations | ~$0.10 |
| **Total** | | ~$5.10/month |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Services-and-Modules]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Security-Threat-Model]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.7]
- [Source: docs/architecture/architecture.md#Security-Architecture]

## Dev Agent Record

### Context Reference

- [docs/stories/0-7-secret-management.context.xml](./0-7-secret-management.context.xml)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

### File List

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-23 | SM Agent (Bob) | Story drafted from Epic 0 tech spec and epic file |
| 2026-01-23 | SM Agent (Bob) | Context XML generated, status: drafted → ready-for-dev |
