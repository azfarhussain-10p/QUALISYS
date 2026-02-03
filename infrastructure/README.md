# QUALISYS Infrastructure

AWS cloud infrastructure managed via Terraform. This directory contains all Infrastructure as Code (IaC) for the QUALISYS platform.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5.0
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) v2.x
- AWS account with appropriate IAM permissions
- MFA device configured for your IAM user

## Quick Start

### 1. Bootstrap State Backend

The Terraform remote state backend (S3 + DynamoDB) must be created first:

```bash
cd infrastructure/terraform/bootstrap
terraform init
terraform apply -var="budget_alert_email=devops@yourdomain.com"
```

### 2. Initialize Main Infrastructure

```bash
cd infrastructure/terraform
cp environments/dev.tfvars.example environments/dev.tfvars
# Edit dev.tfvars with your values
terraform init
terraform plan -var-file="environments/dev.tfvars"
terraform apply -var-file="environments/dev.tfvars"
```

## Directory Structure

```
.github/
├── workflows/
│   ├── pr-checks.yml              # PR validation (lint, format, type-check, tests)
│   ├── deploy-staging.yml         # Auto-deploy on push to main
│   ├── deploy-production.yml      # Manual deploy with approval gate
│   ├── reusable-build.yml         # Reusable Docker build, ECR push, Trivy scanning
│   ├── reusable-test.yml          # Reusable test execution
│   └── reusable-deploy.yml        # Reusable K8s deployment
├── CODEOWNERS                     # Workflow file change approval rules
└── dependabot.yml                 # Keep GitHub Actions up to date

api/
├── Dockerfile                     # API service multi-stage build (node:20-alpine)
└── .dockerignore                  # API build context exclusions

web/
├── Dockerfile                     # Web service multi-stage build (Next.js standalone)
└── .dockerignore                  # Web build context exclusions

playwright-runner/
├── Dockerfile                     # Playwright test runner (mcr.microsoft.com/playwright)
└── .dockerignore                  # Playwright build context exclusions

infrastructure/
├── terraform/
│   ├── backend.tf              # S3 + DynamoDB remote state config
│   ├── providers.tf            # AWS provider configuration
│   ├── variables.tf            # Input variables
│   ├── outputs.tf              # Output values
│   ├── account.tf              # Account alias, Cost Explorer
│   ├── bootstrap/
│   │   └── main.tf             # State backend bootstrap (run first)
│   ├── environments/
│   │   └── dev.tfvars.example  # Example variable values
│   ├── iam/
│   │   ├── roles.tf            # IAM role definitions
│   │   ├── policies.tf         # IAM policy documents
│   │   └── mfa.tf              # MFA enforcement policy
│   ├── monitoring/
│   │   ├── budgets.tf          # AWS Budget alerts + anomaly detection
│   │   └── cloudtrail.tf       # Audit logging
│   ├── vpc/
│   │   ├── main.tf             # VPC, subnets, IGW, subnet groups
│   │   ├── nat.tf              # NAT Gateways, Elastic IPs
│   │   ├── routes.tf           # Route tables, associations
│   │   ├── security-groups.tf  # ALB, K8s, RDS, ElastiCache SGs
│   │   ├── nacls.tf            # Network ACLs (public, private, database)
│   │   ├── flow-logs.tf        # VPC Flow Logs to CloudWatch
│   │   ├── variables.tf        # VPC-specific variables
│   │   └── outputs.tf          # Subnet IDs, SG IDs for downstream
│   ├── eks/
│   │   ├── main.tf             # EKS cluster, OIDC provider, KMS, addons
│   │   ├── node-groups.tf      # General + Playwright node groups
│   │   ├── iam.tf              # Cluster role, node role, IRSA (autoscaler, ALB)
│   │   ├── variables.tf        # EKS-specific variables
│   │   └── outputs.tf          # Cluster endpoint, OIDC ARN for downstream
│   ├── rds/
│   │   ├── main.tf             # RDS instance, KMS, Enhanced Monitoring
│   │   ├── parameter-group.tf  # Custom PostgreSQL 15 parameter group
│   │   ├── secrets.tf          # Secrets Manager secrets, IAM policy
│   │   ├── variables.tf        # RDS-specific variables
│   │   └── outputs.tf          # DB endpoint, secret ARN for downstream
│   ├── elasticache/
│   │   ├── main.tf             # Redis replication group, KMS encryption
│   │   ├── parameter-group.tf  # Custom Redis 7 parameter group
│   │   ├── secrets.tf          # Secrets Manager secret, IAM policy
│   │   ├── variables.tf        # ElastiCache-specific variables
│   │   └── outputs.tf          # Cluster endpoint, secret ARN for downstream
│   ├── ecr/
│   │   ├── main.tf             # ECR repository definitions (3 repos)
│   │   ├── lifecycle-policy.tf # Lifecycle rules (production, tagged, untagged)
│   │   ├── variables.tf        # ECR-specific variables
│   │   └── outputs.tf          # Repository URLs, ARNs for downstream
│   └── secrets/
│       ├── main.tf             # KMS key, JWT + third-party secrets
│       ├── rotation.tf         # DB password rotation Lambda (SAR) + schedule
│       ├── iam.tf              # Category IAM policies, IRSA role, audit alarm
│       ├── variables.tf        # Secrets-specific variables
│       └── outputs.tf          # Secret ARNs, policy ARNs, IRSA role ARN
├── scripts/
│   └── db-init.sql             # PostgreSQL initialization (app_user, RLS test)
├── kubernetes/
│   ├── namespaces/
│   │   ├── namespaces.yaml     # dev, staging, production, playwright-pool, monitoring
│   │   └── resource-quotas.yaml # Per-namespace CPU/memory/pod limits
│   ├── rbac/
│   │   ├── roles.yaml          # ClusterRoles: developer, devops, ci-cd
│   │   ├── bindings.yaml       # ClusterRoleBindings + RoleBindings
│   │   └── aws-auth-configmap.yaml # IAM-to-K8s RBAC mapping
│   ├── cluster-autoscaler/
│   │   └── values.yaml         # Helm values for cluster-autoscaler
│   ├── metrics-server/
│   │   └── values.yaml         # Helm values for metrics-server
│   ├── aws-load-balancer-controller/
│   │   └── values.yaml         # Helm values for AWS ALB controller
│   └── external-secrets/
│       ├── values.yaml             # Helm values for ExternalSecrets Operator
│       ├── cluster-secret-store.yaml # ClusterSecretStore → AWS Secrets Manager
│       └── external-secrets/       # ExternalSecret resources per secret group
│           ├── infra-secrets.yaml      # DB, Redis, JWT
│           ├── llm-secrets.yaml        # OpenAI, Anthropic
│           └── integration-secrets.yaml # OAuth, Email
└── README.md                   # This file
```

## IAM Policy Documentation

### Human User Roles

| Role | Purpose | Policies | MFA Required |
|------|---------|----------|--------------|
| **QualisysDevOpsAdmin** | Infrastructure management, full admin access | PowerUserAccess + IAMFullAccess | Yes |
| **QualisysDeveloper** | Development access: EKS describe, ECR pull, S3 read, CloudWatch logs | QualisysDeveloperPolicy | Yes |
| **QualisysCICD** | Automated deployments: ECR push, EKS staging-only deploy | QualisysCICDPolicy | No (service) |

### Service Account Roles

| Role | Purpose | Policies | Justification |
|------|---------|----------|---------------|
| **QualisysEKSService** | EKS cluster management | AmazonEKSClusterPolicy, AmazonEKSVPCResourceController | Required by EKS for cluster operations |
| **QualisysRDSService** | Database administration | QualisysRDSServicePolicy (describe, snapshot, modify, reboot) | Limited DB management. NO SUPERUSER at PostgreSQL level |
| **QualisysElastiCacheService** | Redis cluster management | QualisysElastiCacheServicePolicy (describe, modify, monitoring) | Cache cluster operations and health monitoring |
| **QualisysECRService** | Container image management | QualisysECRServicePolicy (push, pull, scan, lifecycle) | Image storage and vulnerability scanning |

### Policy Justifications

**QualisysDevOpsAdmin:**
- PowerUserAccess: Full service access needed for infrastructure provisioning via Terraform
- IAMFullAccess: Must manage IAM roles, policies, and users for team onboarding
- MFA required via assume-role condition to prevent unauthorized access

**QualisysDeveloper:**
- EKS read-only: Developers need `kubectl` access for debugging pods and viewing logs
- ECR pull: Pull container images for local testing
- S3 read: Access build artifacts and documentation
- CloudWatch logs: Debug application issues in staging/production
- No write access to infrastructure resources

**QualisysCICD:**
- ECR push: CI/CD pipeline builds and pushes container images
- EKS staging deploy: Automated deployment to staging namespace only
- Explicit deny on secrets: CI/CD CANNOT read Secrets Manager or SSM Parameters (Red Team constraint)
- No pod exec: Prevents CI/CD from executing commands inside running containers
- Short session duration (1 hour): Limits blast radius of compromised CI/CD credentials

**QualisysRDSService:**
- Scoped to `qualisys-*` resources only
- No CreateDBInstance (provisioning done via Terraform)
- Monitoring access for CloudWatch metrics and logs
- CRITICAL: PostgreSQL `app_user` role has NO SUPERUSER, NO BYPASSRLS privileges

### Security Constraints

1. **MFA Enforcement**: All human users denied actions without MFA (QualisysMFAEnforcement policy)
2. **CI/CD Least Privilege**: Cannot read secrets, cannot exec into pods, staging namespace only
3. **Service Account Isolation**: Each service has dedicated role with minimum required permissions
4. **No Superuser**: RDS service account and app_user PostgreSQL role explicitly denied superuser privileges
5. **Credential Storage**: All credentials stored in 1Password, never committed to Git

## Network Architecture

### VPC Design

- **VPC CIDR**: 10.0.0.0/16 (65,536 addresses)
- **Availability Zones**: 2 AZs (us-east-1a, us-east-1b) for high availability
- **Subnet Tiers**: 3 tiers (public, private, database) for defense-in-depth

### Subnet CIDR Allocation

| Subnet Type | AZ-a | AZ-b | Purpose |
|-------------|------|------|---------|
| Public | 10.0.1.0/24 | 10.0.2.0/24 | ALB, NAT Gateways |
| Private | 10.0.10.0/24 | 10.0.11.0/24 | EKS nodes, application pods |
| Database | 10.0.20.0/24 | 10.0.21.0/24 | RDS, ElastiCache (isolated) |

### Routing

| Subnet Type | Default Route | Internet Access |
|-------------|---------------|-----------------|
| Public | 0.0.0.0/0 → IGW | Direct (outbound + inbound) |
| Private | 0.0.0.0/0 → NAT (per-AZ) | Outbound only via NAT Gateway |
| Database | Local only | None (fully isolated) |

### Security Groups

| Security Group | Inbound | Outbound | Consumers |
|----------------|---------|----------|-----------|
| **ALB-SG** | TCP 80, 443 from 0.0.0.0/0 | All to K8s-Nodes-SG | Story 0.13 (Load Balancer) |
| **K8s-Nodes-SG** | All from ALB-SG, All from self | All to 0.0.0.0/0 | Story 0.3 (Kubernetes) |
| **RDS-SG** | TCP 5432 from K8s-Nodes-SG | None | Story 0.4 (PostgreSQL) |
| **ElastiCache-SG** | TCP 6379 from K8s-Nodes-SG | None | Story 0.5 (Redis) |

**Security Group Rules:**
- All rules use SG-to-SG references (not IP-based) for security
- No SSH access from 0.0.0.0/0 — use Systems Manager Session Manager
- Database and cache SGs only accept traffic from K8s nodes

### Network ACLs

| NACL | Inbound | Outbound |
|------|---------|----------|
| **Public** | HTTP (80), HTTPS (443), ephemeral (1024-65535), VPC CIDR | All |
| **Private** | VPC CIDR, ephemeral (1024-65535) | All |
| **Database** | PostgreSQL (5432) + Redis (6379) from private subnets, ephemeral from VPC | Ephemeral to VPC |

### VPC Flow Logs

- **Destination**: CloudWatch Logs (`/aws/vpc/qualisys-flow-logs`)
- **Traffic Type**: ALL (accepted + rejected)
- **Aggregation**: 10-minute intervals
- **Retention**: 30 days

### NAT Gateway Cost

- 2 NAT Gateways (1 per AZ) for high availability
- Estimated cost: ~$64/month ($32/gateway)

## Kubernetes Architecture

### EKS Cluster

- **Cluster Name**: `qualisys-eks`
- **Kubernetes Version**: 1.29 (managed control plane)
- **Endpoint Access**: Private + Public
- **Secrets Encryption**: KMS key with rotation enabled
- **Control Plane Logging**: api, audit, authenticator, controllerManager, scheduler
- **Log Destination**: CloudWatch Logs (`/aws/eks/qualisys-eks/cluster`)
- **EKS Addons**: vpc-cni, kube-proxy, coredns

### Node Groups

| Node Group | Instance Type | Min | Max | Desired | Capacity | Taints | Labels |
|------------|--------------|-----|-----|---------|----------|--------|--------|
| **general** | t3.medium | 2 | 10 | 2 | On-Demand | None | node-type=general |
| **playwright-pool** | c5.xlarge | 5 | 20 | 5 | On-Demand (Spot optional) | workload=playwright:NoSchedule | node-type=playwright |

**Node Security:**
- IMDSv2 required on all nodes (prevents SSRF attacks to metadata service)
- All nodes in private subnets (no direct internet access)
- ECR read-only access for pulling container images

### Namespaces

| Namespace | PSS Level | Resource Quota (CPU/Mem/Pods) | Purpose |
|-----------|-----------|-------------------------------|---------|
| **dev** | baseline (warn: restricted) | 4 cores / 8Gi / 50 | Development testing |
| **staging** | baseline (warn: restricted) | 8 cores / 16Gi / 100 | Pre-production |
| **production** | restricted | 32 cores / 64Gi / 200 | Live traffic |
| **playwright-pool** | baseline (warn: restricted) | 80 cores / 160Gi / 100 | Test runners (Epic 4) |
| **monitoring** | baseline (warn: restricted) | 4 cores / 8Gi / 30 | Prometheus, Grafana |

### RBAC

| Role | dev | staging | production | playwright-pool | monitoring |
|------|-----|---------|------------|-----------------|------------|
| **developer** | Full | Full | Read-only | Read-only | Read-only |
| **devops** | Full | Full | Full | Full | Full |
| **ci-cd** | None | Full | None | Full | None |

**IAM-to-K8s Mapping (aws-auth ConfigMap):**
- `QualisysDevOpsAdmin` IAM role → `qualisys-devops` K8s group
- `QualisysDeveloper` IAM role → `qualisys-developers` K8s group
- `QualisysCICD` IAM role → `qualisys-cicd` K8s group

### Cluster Components

| Component | Deployment | Namespace | IRSA |
|-----------|-----------|-----------|------|
| **Cluster Autoscaler** | Helm chart (~>9.29) | kube-system | qualisys-cluster-autoscaler role |
| **Metrics Server** | Helm chart (~>3.11) | kube-system | N/A |
| **AWS Load Balancer Controller** | Helm chart (~>1.6) | kube-system | qualisys-alb-controller role |

### kubectl Access

```bash
# Update kubeconfig
aws eks update-kubeconfig --name qualisys-eks --region us-east-1

# Switch contexts
kubectl config use-context arn:aws:eks:us-east-1:<ACCOUNT_ID>:cluster/qualisys-eks

# Verify access
kubectl get nodes
kubectl get namespaces

# Test RBAC permissions
kubectl auth can-i create pods --namespace production  # developer: no
kubectl auth can-i create pods --namespace staging     # developer: yes
kubectl auth can-i '*' '*'                             # devops: yes

# Verify metrics
kubectl top nodes
kubectl top pods -A
```

### Helm Chart Installation

```bash
# 1. Cluster Autoscaler
helm repo add autoscaler https://kubernetes.github.io/autoscaler
helm install cluster-autoscaler autoscaler/cluster-autoscaler \
  -n kube-system -f kubernetes/cluster-autoscaler/values.yaml

# 2. Metrics Server
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server
helm install metrics-server metrics-server/metrics-server \
  -n kube-system -f kubernetes/metrics-server/values.yaml

# 3. AWS Load Balancer Controller
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system -f kubernetes/aws-load-balancer-controller/values.yaml
```

## PostgreSQL Database Architecture

### RDS Instance

- **Engine**: PostgreSQL 15.4 (managed by AWS RDS)
- **Instance Name**: `qualisys-db`
- **Database Name**: `qualisys_master`
- **Encryption**: KMS with key rotation enabled
- **Storage**: gp3, 20GB initial, autoscaling up to 100GB

### Environment Configuration

| Setting | dev/staging | production |
|---------|-------------|------------|
| **Instance Class** | db.t3.medium (2 vCPU, 4GB) | db.r5.large (2 vCPU, 16GB) |
| **Multi-AZ** | No | Yes |
| **Deletion Protection** | No | Yes |
| **Final Snapshot** | Skipped | Required |

### Backup & Maintenance

| Setting | Value |
|---------|-------|
| **Backup Retention** | 7 days |
| **Backup Window** | 03:00-04:00 UTC |
| **Maintenance Window** | Sun 04:00-05:00 UTC |
| **Performance Insights** | Enabled (7-day retention) |
| **Enhanced Monitoring** | 60-second granularity |

### Parameter Group (`qualisys-postgres15`)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| max_connections | 200 | Support 100+ concurrent pods |
| shared_buffers | 25% of RAM | PostgreSQL recommendation |
| work_mem | 64MB | Complex query support |
| maintenance_work_mem | 512MB | Faster vacuums, index builds |
| effective_cache_size | 50% of RAM | SSD-backed storage |
| pg_stat_statements.track | all | Query performance monitoring |
| log_min_duration_statement | 1000ms | Slow query logging |
| row_security | on | RLS enforcement |

### Multi-Tenant Design

- **Strategy**: Schema-per-tenant (each organization gets isolated PostgreSQL schema)
- **RLS**: Row-Level Security as defense-in-depth layer
- **Master Database**: `qualisys_master` (created by Terraform)
- **Application User**: `app_user` (NO SUPERUSER, NO BYPASSRLS — Red Team requirement)

```
qualisys_master/
├── public/           # Shared schema (system tables)
├── tenant_{slug_1}/  # Org 1 schema (created by Epic 1)
├── tenant_{slug_2}/  # Org 2 schema
└── ...
```

### Secrets Manager

| Secret | Path | Purpose |
|--------|------|---------|
| Master credentials | `qualisys/database/master` | Admin operations |
| App connection | `qualisys/database/connection` | K8s pod access (IRSA) |

Both secrets are KMS-encrypted. The connection secret includes a full `connection_uri` for convenience.

### Database Initialization

After `terraform apply`, run the initialization script to create `app_user` and verify RLS:

```bash
# 1. Get master password
MASTER_PASS=$(aws secretsmanager get-secret-value \
  --secret-id qualisys/database/master \
  --query 'SecretString' --output text | jq -r '.password')

# 2. Get app_user password
APP_PASS=$(aws secretsmanager get-secret-value \
  --secret-id qualisys/database/connection \
  --query 'SecretString' --output text | jq -r '.password')

# 3. Get RDS endpoint
DB_HOST=$(terraform output -raw db_address)

# 4. Run initialization script
PGPASSWORD=$MASTER_PASS psql \
  -h $DB_HOST -U qualisys_admin -d qualisys_master \
  -v app_user_password="'$APP_PASS'" \
  -f infrastructure/scripts/db-init.sql
```

### Database Troubleshooting

**Cannot connect to RDS:**
1. Verify you are on a K8s node or have VPN access to private subnets
2. RDS is not publicly accessible — use `kubectl port-forward` or a bastion
3. Check security group allows 5432 from your source: `aws ec2 describe-security-groups --group-ids <rds-sg-id>`

**app_user connection refused:**
1. Verify `db-init.sql` has been run to create the `app_user` role
2. Check Secrets Manager for correct password: `aws secretsmanager get-secret-value --secret-id qualisys/database/connection`
3. Verify SSL mode: connection URI must include `?sslmode=require`

**Performance issues:**
1. Check Performance Insights: AWS Console > RDS > Performance Insights
2. Review slow queries: `SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;`
3. Verify parameter group is attached: `aws rds describe-db-instances --db-instance-identifier qualisys-db --query 'DBInstances[0].DBParameterGroups'`

**RLS not enforcing:**
1. Verify `row_security = on` in parameter group
2. Check RLS is enabled on table: `SELECT rowsecurity FROM pg_tables WHERE tablename = '<table>'`
3. Verify `app_user` has NOBYPASSRLS: `SELECT rolbypassrls FROM pg_roles WHERE rolname = 'app_user'`
4. Superusers bypass RLS — ensure application uses `app_user`, never master user

## Redis Caching Architecture

### ElastiCache Cluster

- **Engine**: Redis 7.0 (managed by AWS ElastiCache)
- **Cluster Name**: `qualisys-redis`
- **Cluster Mode**: Enabled (slot-based sharding)
- **Encryption**: KMS (at rest) + TLS (in transit)
- **Auth**: Password-based auth token (64-char alphanumeric)

### Environment Configuration

| Setting | dev | staging | production |
|---------|-----|---------|------------|
| **Node Type** | cache.t3.micro (0.5 GB) | cache.t3.small (1.37 GB) | cache.r5.large (13.07 GB) |
| **Shards** | 1 | 2 | 2 |
| **Replicas/Shard** | 0 | 1 | 1 |
| **Total Nodes** | 1 | 4 | 4 |
| **Multi-AZ** | No | Yes | Yes |
| **Automatic Failover** | No | Yes | Yes |

### Parameter Group (`qualisys-redis7`)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| maxmemory-policy | allkeys-lru | Evict least recently used keys when memory full |
| tcp-keepalive | 300 | Keep connections alive, detect dead connections |
| timeout | 0 | No idle timeout for persistent application connections |
| notify-keyspace-events | Ex | Monitor expired and evicted key events |
| cluster-enabled | yes | Required for cluster mode with multiple shards |

### Maintenance & Snapshots

| Setting | Value |
|---------|-------|
| **Snapshot Retention** | 7 days |
| **Snapshot Window** | 05:00-06:00 UTC |
| **Maintenance Window** | Sun 06:00-07:00 UTC |

### Secrets Manager

| Secret | Path | Purpose |
|--------|------|---------|
| Redis connection | `qualisys/redis/connection` | K8s pod access (IRSA) |

The connection secret includes: `primary_endpoint`, `reader_endpoint`, `port`, `auth_token`, `ssl_enabled`, and a `connection_uri` using the `rediss://` scheme (TLS).

### Key Namespacing Strategy (Tenant Isolation)

Redis tenant isolation is enforced at the **application layer** via key namespacing. All keys MUST follow the format:

```
{tenant_id}:{scope}:{key_identifier}
```

**Scope Categories:**

| Scope | Key Format | TTL | Use Case |
|-------|-----------|-----|----------|
| `session` | `{tenant_id}:session:{user_id}` | 24 hours | User session data |
| `llm_cache` | `{tenant_id}:llm_cache:{prompt_hash}` | 1-7 days | Cached AI agent responses |
| `rate_limit` | `{tenant_id}:rate_limit:{api_key}` | 1 minute | Rate limiting counters |
| `temp` | `{tenant_id}:temp:{operation_id}` | 1 hour | Temporary processing data |

**Examples:**

```
# Session management
tenant_acme:session:user_12345
tenant_globex:session:user_67890

# LLM response caching
tenant_acme:llm_cache:prompt_hash_abc123
tenant_acme:llm_cache:agent_requirements_doc_v1

# Rate limiting
tenant_acme:rate_limit:api_user_12345
tenant_globex:rate_limit:api_user_67890

# Temporary data
tenant_acme:temp:upload_progress_xyz789
```

**Security Constraints:**
- Application middleware MUST prefix all keys with the authenticated tenant ID
- No Redis command should operate without a tenant-scoped key
- `KEYS *` and `FLUSHDB` are restricted to admin operations only
- Enforced at application layer (Epic 1 implementation) — not at Redis level

### Redis Connection

```bash
# Retrieve connection info
aws secretsmanager get-secret-value \
  --secret-id qualisys/redis/connection \
  --query 'SecretString' --output text | jq .

# Test connectivity (from K8s pod)
kubectl run redis-test --rm -it --image=redis:7 -- \
  redis-cli -h <configuration_endpoint> --tls -a <auth_token> PING

# Verify cluster info
kubectl run redis-test --rm -it --image=redis:7 -- \
  redis-cli -h <configuration_endpoint> --tls -a <auth_token> CLUSTER INFO
```

### Redis Troubleshooting

**Cannot connect to Redis:**
1. Verify you are on a K8s node or have VPN access to private subnets
2. ElastiCache is not publicly accessible — use `kubectl port-forward` or a pod in the cluster
3. Check security group allows 6379 from your source: `aws ec2 describe-security-groups --group-ids <elasticache-sg-id>`
4. Ensure TLS is used (`--tls` flag in redis-cli, `rediss://` scheme in client)

**Auth token rejected:**
1. Retrieve current token: `aws secretsmanager get-secret-value --secret-id qualisys/redis/connection`
2. Verify transit encryption is enabled (auth token requires TLS)
3. Ensure client uses the `AUTH` command or passes token in connection URI

**Cluster mode issues:**
1. Verify parameter group has `cluster-enabled=yes`: `aws elasticache describe-cache-parameters --cache-parameter-group-name qualisys-redis7`
2. Ensure Redis client supports cluster mode (e.g., `ioredis` with `Cluster` class, `redis-py` with `RedisCluster`)
3. Check cluster health: `redis-cli -h <endpoint> --tls -a <token> CLUSTER INFO`

**High memory usage:**
1. Check eviction policy: `CONFIG GET maxmemory-policy` should return `allkeys-lru`
2. Monitor keyspace: `redis-cli -h <endpoint> --tls -a <token> INFO keyspace`
3. Check evicted keys metric in CloudWatch: `ElastiCache > Evictions`

**Failover not working (staging/production):**
1. Verify automatic failover is enabled: `aws elasticache describe-replication-groups --replication-group-id qualisys-redis`
2. Multi-AZ requires at least 1 replica per shard
3. Dev environment has no replicas — failover is not available

## Container Registry (ECR)

### Repositories

| Repository | Purpose | Scan on Push | Tag Immutability |
|------------|---------|--------------|------------------|
| **qualisys-api** | Backend API service | Yes | IMMUTABLE |
| **qualisys-web** | Frontend Next.js application | Yes | IMMUTABLE |
| **playwright-runner** | Test execution container | Yes | IMMUTABLE |

- **Encryption**: AES-256 (AWS-managed key) at rest
- **Access**: Private only — IAM authentication required, no public access
- **Scanning**: Basic scanning on push (vulnerability detection)

### Image Tagging Strategy

| Tag Pattern | Purpose | Example |
|-------------|---------|---------|
| `{git-sha}` | Immutable reference to exact commit | `abc123def` |
| `{branch}-{timestamp}` | Branch builds with timestamp | `main-20260123-143022` |
| `production-{version}` | Production releases (kept indefinitely) | `production-v1.2.3` |
| `staging-{date}` | Staging deployments | `staging-20260123` |

**Note**: Tag immutability is enabled — each tag can only be used once. Do not use `latest` tag.

### Lifecycle Policy

| Priority | Rule | Action |
|----------|------|--------|
| 1 | Images tagged `production-*` | Keep indefinitely (up to 9999) |
| 2 | All other tagged images | Keep last 10, expire older |
| 3 | Untagged images | Delete after 7 days |

### IAM Access

| Role | Access | Source |
|------|--------|--------|
| **QualisysCICD** | Push + Pull (`qualisys-*` repos) | `iam/policies.tf` (Story 0.1) |
| **EKS Node** | Pull (all ECR repos) | `AmazonEC2ContainerRegistryReadOnly` (Story 0.3) |
| **QualisysDeveloper** | Pull only | `iam/policies.tf` (Story 0.1) |
| **QualisysECRService** | Full management | `iam/policies.tf` (Story 0.1) |

### CI/CD Image Push Workflow

```bash
# 1. Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# 2. Build image
docker build -t qualisys-api:$(git rev-parse --short HEAD) .

# 3. Tag for ECR
docker tag qualisys-api:$(git rev-parse --short HEAD) \
  <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/qualisys-api:$(git rev-parse --short HEAD)

# 4. Push to ECR
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/qualisys-api:$(git rev-parse --short HEAD)

# 5. Verify scan results
aws ecr describe-image-scan-findings \
  --repository-name qualisys-api \
  --image-id imageTag=$(git rev-parse --short HEAD)
```

### ECR Troubleshooting

**Authentication failed:**
1. Re-authenticate: `aws ecr get-login-password | docker login --username AWS --password-stdin <registry>`
2. ECR tokens expire after 12 hours — re-run login before each push session
3. Verify IAM role has `ecr:GetAuthorizationToken` permission

**Push rejected (tag already exists):**
1. Tag immutability is enabled — each tag can only be used once
2. Use unique tags: git-sha, branch-timestamp, or version-based
3. Do not attempt to overwrite existing tags

**Image scan shows vulnerabilities:**
1. Review findings: `aws ecr describe-image-scan-findings --repository-name <repo> --image-id imageTag=<tag>`
2. Severity levels: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL
3. Update base images to patch vulnerabilities before deploying to production
4. Check AWS Inspector for enhanced scanning recommendations

**Lifecycle policy not cleaning up:**
1. Lifecycle policies run asynchronously (may take up to 24 hours)
2. Preview policy: `aws ecr get-lifecycle-policy-preview --repository-name <repo>`
3. Production-tagged images (`production-*`) are protected from cleanup

## Secret Management

### Secrets Overview

All application secrets are stored in AWS Secrets Manager. No secrets are committed to Git or baked into Docker images. Applications retrieve secrets at runtime via the ExternalSecrets Operator, which syncs AWS secrets to Kubernetes Secrets.

### Secret Naming Convention

```
qualisys/{category}/{name}
```

| Category | Secret ID | Fields | Consumers | Source |
|----------|-----------|--------|-----------|--------|
| database | `qualisys/database/connection` | host, port, database, username, password, connection_uri | API pods | Story 0.4 |
| database | `qualisys/database/master` | host, port, database, username, password | Admin ops only | Story 0.4 |
| redis | `qualisys/redis/connection` | primary_endpoint, reader_endpoint, port, auth_token, connection_uri | API pods | Story 0.5 |
| jwt | `qualisys/jwt/signing-key` | secret (256-bit) | API pods | Story 0.7 |
| llm | `qualisys/llm/openai` | api_key | AI Agent pods | Story 0.7 |
| llm | `qualisys/llm/anthropic` | api_key | AI Agent pods | Story 0.7 |
| oauth | `qualisys/oauth/google` | client_id, client_secret | API pods | Story 0.7 |
| email | `qualisys/email/sendgrid` | api_key | API pods | Story 0.7 |

### IAM Access Policies (Least Privilege)

| Policy | Secrets Access | Consumers |
|--------|---------------|-----------|
| `qualisys-secrets-read-infra` | database, redis, jwt | API pod IRSA roles |
| `qualisys-secrets-read-llm` | openai, anthropic | AI agent pod IRSA roles |
| `qualisys-secrets-read-integrations` | oauth, email | API pod IRSA roles |
| `qualisys-external-secrets` | All `qualisys/*` secrets | ExternalSecrets Operator |

### ExternalSecrets Operator

The ExternalSecrets Operator (ESO) syncs secrets from AWS Secrets Manager into Kubernetes Secrets, which pods consume as environment variables or volume mounts.

**Architecture:**
```
AWS Secrets Manager  →  ExternalSecrets Operator (IRSA)  →  K8s Secrets  →  Pods
```

**Installation:**
```bash
# 1. Install ExternalSecrets Operator via Helm
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace \
  -f kubernetes/external-secrets/values.yaml

# 2. Apply ClusterSecretStore
kubectl apply -f kubernetes/external-secrets/cluster-secret-store.yaml

# 3. Apply ExternalSecret resources per namespace
kubectl apply -f kubernetes/external-secrets/external-secrets/infra-secrets.yaml -n production
kubectl apply -f kubernetes/external-secrets/external-secrets/llm-secrets.yaml -n production
kubectl apply -f kubernetes/external-secrets/external-secrets/integration-secrets.yaml -n production

# Repeat for dev and staging namespaces

# 4. Verify sync status
kubectl get externalsecrets -A
kubectl get secrets -n production
```

**Kubernetes Secrets Created:**

| K8s Secret Name | Source ExternalSecret | Keys |
|-----------------|----------------------|------|
| `database-credentials` | infra-secrets.yaml | DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_URL |
| `redis-credentials` | infra-secrets.yaml | REDIS_HOST, REDIS_READER_HOST, REDIS_PORT, REDIS_AUTH_TOKEN, REDIS_URL |
| `jwt-signing-key` | infra-secrets.yaml | JWT_SECRET |
| `llm-credentials` | llm-secrets.yaml | OPENAI_API_KEY, ANTHROPIC_API_KEY |
| `oauth-credentials` | integration-secrets.yaml | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET |
| `email-credentials` | integration-secrets.yaml | SENDGRID_API_KEY |

### Secret Rotation

| Secret | Rotation Period | Method | Automated |
|--------|-----------------|--------|-----------|
| Database password | 90 days | AWS-managed Lambda (SAR) | Yes |
| Redis auth token | Manual | Coordinate with ElastiCache | No |
| JWT signing key | Annual | Manual with key versioning | No |
| LLM API keys | Quarterly | Manual (provider regeneration) | No |
| OAuth credentials | Annual | Manual (Google Cloud Console) | No |
| Email API key | Annual | Manual (SendGrid dashboard) | No |

**Database rotation** uses the AWS-provided `SecretsManagerRDSPostgreSQLRotationSingleUser` Lambda, deployed via Serverless Application Repository. The rotation Lambda runs in private subnets with access to both RDS (via security group) and Secrets Manager API (via NAT Gateway).

**Rotation alerts** are sent to the `qualisys-secrets-alerts` SNS topic via EventBridge rules that capture rotation success/failure events.

### Setting Third-Party API Keys

After `terraform apply`, update placeholder secrets with actual API keys:

```bash
# OpenAI
aws secretsmanager put-secret-value \
  --secret-id qualisys/llm/openai \
  --secret-string '{"api_key":"sk-your-actual-openai-key"}'

# Anthropic
aws secretsmanager put-secret-value \
  --secret-id qualisys/llm/anthropic \
  --secret-string '{"api_key":"sk-ant-your-actual-anthropic-key"}'

# Google OAuth
aws secretsmanager put-secret-value \
  --secret-id qualisys/oauth/google \
  --secret-string '{"client_id":"your-client-id.apps.googleusercontent.com","client_secret":"your-secret"}'

# SendGrid
aws secretsmanager put-secret-value \
  --secret-id qualisys/email/sendgrid \
  --secret-string '{"api_key":"SG.your-actual-sendgrid-key"}'
```

### Audit Logging

- **CloudTrail**: All `secretsmanager:GetSecretValue` and `secretsmanager:DescribeSecret` calls are logged by the existing CloudTrail trail (`qualisys-management-trail` from Story 0.1)
- **Unauthorized access detection**: EventBridge rule captures `AccessDeniedException` events on Secrets Manager → SNS notification + CloudWatch alarm
- **Rotation monitoring**: EventBridge rule captures rotation success/failure → SNS notification

### Secret Management Troubleshooting

**ExternalSecrets not syncing:**
1. Check operator status: `kubectl get pods -n external-secrets`
2. Check ClusterSecretStore: `kubectl get clustersecretstore aws-secrets-manager -o yaml`
3. Check ExternalSecret status: `kubectl get externalsecret <name> -n <namespace> -o yaml`
4. Verify IRSA annotation on service account: `kubectl get sa external-secrets-sa -n external-secrets -o yaml`
5. Check IRSA role trust policy includes the correct OIDC provider and service account

**Secret rotation failed:**
1. Check rotation Lambda logs: `aws logs tail /aws/lambda/qualisys-db-password-rotation`
2. Verify Lambda can reach RDS: check security group rules (rotation-lambda-sg → rds-sg on 5432)
3. Verify Lambda can reach Secrets Manager: Lambda is in private subnets with NAT access
4. Manual rotation: `aws secretsmanager rotate-secret --secret-id qualisys/database/connection`

**Cannot read secret (AccessDenied):**
1. Verify IAM role has the correct category policy attached (infra, llm, or integrations)
2. Check KMS key policy allows decrypt via Secrets Manager
3. Verify IRSA is working: `kubectl exec <pod> -- env | grep AWS_WEB_IDENTITY_TOKEN_FILE`

**Manual emergency rotation:**
```bash
# Generate new database password
NEW_PASS=$(openssl rand -base64 32)

# Update in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id qualisys/database/connection \
  --secret-string "{\"engine\":\"postgres\",\"host\":\"<host>\",\"port\":5432,\"database\":\"qualisys_master\",\"username\":\"app_user\",\"password\":\"${NEW_PASS}\",\"connection_uri\":\"postgresql://app_user:${NEW_PASS}@<host>:5432/qualisys_master?sslmode=require\"}"

# Update in PostgreSQL
PGPASSWORD=<master_pass> psql -h <host> -U qualisys_admin -d qualisys_master \
  -c "ALTER USER app_user WITH PASSWORD '${NEW_PASS}';"

# Restart pods to pick up new secret (ExternalSecrets refreshes within 1h, or restart immediately)
kubectl rollout restart deployment -n production
```

## Cost Monitoring

### Budget Alerts

| Threshold | Alert At | Type |
|-----------|----------|------|
| $500/month | 80% ($400) and 100% ($500) | Actual spend |
| $1,000/month | 80% ($800) and 100% ($1,000) | Actual spend |
| $2,000/month | 80% ($1,600) and 100% ($2,000) | Actual spend |
| Anomaly | 150% of forecasted spend | Forecasted |

All alerts sent to SNS topic → email notification to DevOps Lead.

### Cost Anomaly Detection

AWS Cost Anomaly Detection monitors all services for unusual spending patterns. Alerts triggered when anomaly impact exceeds $50. Daily digest sent to budget alerts SNS topic.

## Audit Logging

### CloudTrail

- **Scope**: All regions, management events, global service events
- **Storage**: S3 bucket `qualisys-cloudtrail-logs` with encryption
- **Retention**: 90 days (lifecycle policy auto-deletes older logs)
- **Validation**: Log file integrity validation enabled

## Terraform State

### Remote Backend

- **Bucket**: `qualisys-terraform-state` (S3 with versioning + AES-256 encryption)
- **Lock Table**: `terraform-state-lock` (DynamoDB, prevents concurrent modifications)
- **Access**: Restricted to QualisysDevOpsAdmin role only

### State Safety

- S3 versioning enables rollback of corrupted state
- DynamoDB locking prevents concurrent `terraform apply` (Pre-mortem finding)
- State bucket policy denies non-DevOps access

## Troubleshooting

### Common IAM Issues

**"Access Denied" when assuming role:**
1. Verify MFA is configured: `aws iam list-mfa-devices --user-name <your-user>`
2. Use MFA token when assuming role: `aws sts assume-role --role-arn <role-arn> --serial-number <mfa-arn> --token-code <code>`
3. Check IAM group membership: `aws iam list-groups-for-user --user-name <your-user>`

**"Unable to assume QualisysCICD role":**
1. CI/CD role does not require MFA (service account)
2. Verify the calling entity is listed in the trust policy
3. Check CloudTrail for detailed error: `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRole`

**Terraform state lock stuck:**
1. Check DynamoDB for lock: `aws dynamodb scan --table-name terraform-state-lock`
2. Force unlock (use with caution): `terraform force-unlock <lock-id>`
3. Verify no other `terraform apply` is running

**Budget alerts not received:**
1. Confirm SNS subscription: `aws sns list-subscriptions-by-topic --topic-arn <arn>`
2. Check email spam folder for SNS confirmation
3. Verify budget exists: `aws budgets describe-budgets --account-id <id>`

**CloudTrail not logging:**
1. Check trail status: `aws cloudtrail get-trail-status --name qualisys-management-trail`
2. Verify S3 bucket policy allows CloudTrail writes
3. Check for S3 bucket access errors in CloudTrail console

### Common EKS Issues

**Nodes not joining cluster:**
1. Verify aws-auth ConfigMap includes node role: `kubectl get configmap aws-auth -n kube-system -o yaml`
2. Check node group status: `aws eks describe-nodegroup --cluster-name qualisys-eks --nodegroup-name qualisys-general`
3. Verify nodes can reach API server: check VPC security groups and NACLs
4. Check node IAM role has required policies: `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly`

**kubectl connection refused:**
1. Update kubeconfig: `aws eks update-kubeconfig --name qualisys-eks --region us-east-1`
2. Verify cluster endpoint: `aws eks describe-cluster --name qualisys-eks --query 'cluster.endpoint'`
3. Check IAM role mapping in aws-auth ConfigMap

**Pods stuck in Pending (playwright-pool):**
1. Verify toleration matches taint: `workload=playwright:NoSchedule`
2. Check node capacity: `kubectl describe node <node-name>`
3. Verify cluster autoscaler is running: `kubectl get pods -n kube-system -l app.kubernetes.io/name=cluster-autoscaler`
4. Check autoscaler logs: `kubectl logs -n kube-system -l app.kubernetes.io/name=cluster-autoscaler`

**Pod rejected by PSS (production namespace):**
1. Production uses `restricted` PSS level
2. Check pod spec for violations: `kubectl describe pod <pod-name> -n production`
3. Common violations: running as root, privileged containers, hostPath mounts

### Credential Management

- **1Password vault**: `QUALISYS Infrastructure` (create manually)
- **Access keys**: Generate via IAM console, store immediately in 1Password
- **Rotation**: Rotate access keys every 90 days
- **Audit**: Run `git log --all -p -- '*.pem' '*.key' 'credentials*'` to check for leaked credentials
- **Scanning**: Use `git-secrets --scan` or `trufflehog filesystem .` to detect secrets in repo

## CI/CD Pipeline (GitHub Actions)

### Workflow Architecture

```
PR Checks (pull_request to main)
  └─ lint → format-check → type-check → unit-tests → integration-tests

Deploy Staging (push to main)
  └─ build-api ─┐
  └─ build-web ─┤→ deploy-staging → notify
                │
Deploy Production (workflow_dispatch - manual)
  └─ validate → deploy-production (approval gate) → smoke-tests → notify
```

### Workflows

| Workflow | Trigger | Purpose | File |
|----------|---------|---------|------|
| **PR Checks** | `pull_request` to main | Lint, format, type-check, unit + integration tests | `.github/workflows/pr-checks.yml` |
| **Deploy Staging** | `push` to main | Build images, deploy to staging namespace | `.github/workflows/deploy-staging.yml` |
| **Deploy Production** | `workflow_dispatch` (manual) | Deploy tested image to production with approval | `.github/workflows/deploy-production.yml` |
| **Reusable Build** | `workflow_call` | Docker build and ECR push | `.github/workflows/reusable-build.yml` |
| **Reusable Test** | `workflow_call` | Test execution (unit, integration, e2e) | `.github/workflows/reusable-test.yml` |
| **Reusable Deploy** | `workflow_call` | K8s deployment via kubectl | `.github/workflows/reusable-deploy.yml` |

### Workflow Permissions (Least Privilege)

| Workflow | contents | pull-requests | packages | id-token |
|----------|----------|---------------|----------|----------|
| pr-checks | read | write | - | - |
| deploy-staging | read | - | write | write |
| deploy-production | read | - | write | write |
| reusable-* | read | - | - | - |

### GitHub Actions Secrets Setup

Configure these secrets in the repository settings or via `gh secret set`:

```bash
# Required secrets (from Stories 0.1, 0.3, 0.6)
gh secret set AWS_ACCESS_KEY_ID --body "<CI/CD IAM user access key>"
gh secret set AWS_SECRET_ACCESS_KEY --body "<CI/CD IAM user secret key>"
gh secret set AWS_REGION --body "us-east-1"
gh secret set KUBECONFIG_BASE64 --body "$(base64 < ~/.kube/config)"
gh secret set ECR_REGISTRY --body "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com"

# Optional
gh secret set SLACK_WEBHOOK_URL --body "<Slack incoming webhook URL>"
```

### GitHub Environments Setup

```bash
# Create staging environment (no protection rules)
gh api repos/{owner}/{repo}/environments/staging -X PUT

# Create production environment with required reviewers
gh api repos/{owner}/{repo}/environments/production -X PUT \
  -f 'reviewers[][type]=User' \
  -f 'reviewers[][id]=<devops_lead_user_id>' \
  -f 'reviewers[][type]=User' \
  -f 'reviewers[][id]=<tech_lead_user_id>' \
  -F 'wait_timer=5'
```

### Branch Protection

The `.github/CODEOWNERS` file requires DevOps Lead and Tech Lead approval for any changes to workflow files. Enable CODEOWNERS enforcement in repository settings:

1. Go to Settings > Branches > Branch protection rules
2. Add rule for `main` branch
3. Enable "Require a pull request before merging"
4. Enable "Require review from Code Owners"

### Deploying to Production

```bash
# 1. Find the image tag from the staging deployment
gh run list --workflow=deploy-staging.yml --limit=5

# 2. Trigger production deployment with the tested image tag
gh workflow run deploy-production.yml -f image_tag=<git-sha>

# 3. Approve in GitHub UI when prompted (production environment protection)

# 4. Monitor deployment
gh run watch
```

### CI/CD Troubleshooting

**PR checks failing on lint:**
1. Run locally: `npm run lint` and `ruff check .`
2. Auto-fix: `npm run lint -- --fix` and `ruff check . --fix`
3. Check Node.js version matches workflow (v20)

**ECR push denied:**
1. Verify CI/CD IAM user has `QualisysCICDPolicy` attached
2. Check ECR repository exists: `aws ecr describe-repositories --repository-names qualisys-api`
3. ECR login tokens expire after 12 hours

**Deployment rollout timeout:**
1. Check pod events: `kubectl describe pod <pod-name> -n <namespace>`
2. Common causes: image pull errors, insufficient resources, failed health checks
3. Rollback: `kubectl rollout undo deployment/<name> -n <namespace>`

**Production approval not appearing:**
1. Verify GitHub Environment "production" exists with required reviewers
2. Verify workflow uses `environment: production` in the deploy job
3. Check organization settings allow environment protection rules

## Docker Build Automation

### Dockerfiles

| Service | Dockerfile | Base Image | Target Size | Stages |
|---------|-----------|------------|-------------|--------|
| **qualisys-api** | `api/Dockerfile` | `node:20-alpine` | <200MB | deps → builder → runner |
| **qualisys-web** | `web/Dockerfile` | `node:20-alpine` | <300MB | deps → builder → runner |
| **playwright-runner** | `playwright-runner/Dockerfile` | `mcr.microsoft.com/playwright:v1.40.0-jammy` | <2GB | deps → runner |

### Build Features

- **Multi-stage builds**: Separate build and runtime stages minimize image size and attack surface
- **BuildKit**: All Dockerfiles use `# syntax=docker/dockerfile:1` and `--mount=type=cache` for package manager caching
- **Non-root users**: API runs as `appuser:1001`, Web runs as `nextjs:1001`, Playwright runs as `pwuser`
- **Health checks**: API and Web Dockerfiles include `HEALTHCHECK` instructions
- **GitHub Actions cache**: `cache-from: type=gha` / `cache-to: type=gha,mode=max` for layer caching across builds

### Vulnerability Scanning (Trivy)

The `reusable-build.yml` workflow includes two Trivy scans:

1. **Vulnerability scan**: Fails build on HIGH/CRITICAL findings (SARIF format uploaded to GitHub Security tab)
2. **Secret scan**: Fails build if secrets are detected baked into the image

```bash
# Run Trivy locally
trivy image --severity HIGH,CRITICAL qualisys-api:latest
trivy image --scanners secret qualisys-api:latest
```

### Image Tagging Strategy

| Tag Pattern | When Applied | Example | Purpose |
|-------------|--------------|---------|---------|
| `{git-sha}` | Every build | `a1b2c3d` | Immutable reference (ECR tag immutability) |
| `{branch}-{timestamp}` | Every build | `main-20260123-143022` | Branch tracking |
| `staging-{date}` | Staging deploy | `staging-20260123` | Environment tracking |
| `production-v{X.Y.Z}` | Release | `production-v1.2.3` | Semantic version |

### Podman Compatibility

All Dockerfiles produce **OCI-compliant images** and are fully compatible with [Podman](https://podman.io/). Per 10Pearls workstation policy (see `docs/sprint-change-proposal-2026-01-24.md`), developer machines use Podman instead of Docker Desktop. This does **not** affect:

- **CI/CD pipelines** — GitHub-hosted runners use Docker (not subject to workstation policy)
- **Dockerfiles** — OCI standard, work identically with both Docker and Podman
- **ECR** — Podman supports ECR authentication via `podman login`
- **Kubernetes** — Uses containerd runtime, unrelated to local build tooling

To build locally with Podman, simply replace `docker` with `podman` in all commands below.

### Building Locally

```bash
# Build API image (use `podman` instead of `docker` on developer workstations)
DOCKER_BUILDKIT=1 docker build -t qualisys-api:dev ./api

# Build Web image
DOCKER_BUILDKIT=1 docker build -t qualisys-web:dev ./web

# Build Playwright runner
DOCKER_BUILDKIT=1 docker build -t playwright-runner:dev ./playwright-runner

# Verify image sizes
docker images | grep qualisys

# Run locally
docker run -p 3000:3000 qualisys-api:dev
docker run -p 3001:3000 qualisys-web:dev

# Run Playwright tests
docker run playwright-runner:dev
docker run playwright-runner:dev npx playwright test --project=chromium
```

> **Podman users**: Replace `docker` with `podman` in all commands above. Podman supports BuildKit syntax natively. For ECR authentication: `aws ecr get-login-password | podman login --username AWS --password-stdin <registry>`

### Docker Build Troubleshooting

**Build fails with BuildKit cache error:**
1. Ensure Docker version supports BuildKit (20.10+)
2. Set `DOCKER_BUILDKIT=1` environment variable
3. Clear cache: `docker builder prune`

**Image size too large:**
1. Verify multi-stage build is used (final stage should only have runtime files)
2. Check `.dockerignore` excludes `node_modules/`, `.git/`, test artifacts
3. Use `docker history <image>` to identify large layers
4. Ensure `npm ci --omit=dev` is used in production stage

**Trivy scan fails on HIGH vulnerability:**
1. Review finding: Check if it's in a base image or application dependency
2. Update base image: `docker pull node:20-alpine` to get latest patches
3. Update dependencies: `npm audit fix`
4. If false positive: document exception in `.trivyignore` file

**Health check failing:**
1. Verify application starts and responds on the health endpoint
2. Check port matches (`EXPOSE` and `HEALTHCHECK` port must match)
3. Increase `--start-period` if application needs more startup time

## Automated Test Execution on PR

### Test Architecture

PR checks run all test suites automatically when a Pull Request targets `main`:

```
PR Checks Pipeline
  ├─ lint (ESLint + Ruff)
  ├─ format-check (Prettier + Black)
  ├─ type-check (TypeScript + mypy)
  │
  ├─ unit-tests (Node 18 + 20 matrix)    ← after lint/format/type
  ├─ integration-tests (PostgreSQL + Redis)
  ├─ e2e-tests (Playwright critical paths)
  │
  └─ test-summary (PR comment)           ← after all test jobs
```

### Test Suites

| Suite | Framework | Location | Runs On | Retry |
|-------|-----------|----------|---------|-------|
| **Unit** | Jest | `api/__tests__/unit/`, `web/__tests__/unit/` | Node 18 + 20 (matrix) | 3x |
| **Integration** | Jest + Supertest | `api/__tests__/integration/` | Node 20, PostgreSQL 15, Redis 7 | 3x |
| **E2E (Critical)** | Playwright | `e2e/tests/critical/` | Chromium headless | 2x |
| **E2E (Full)** | Playwright | `e2e/tests/full/` | Chromium + Firefox + WebKit | 2x |

### Coverage Configuration

| Metric | Threshold |
|--------|-----------|
| Line coverage | 80% |
| Function coverage | 80% |
| Statement coverage | 80% |
| Branch coverage | 70% |

Coverage is collected by Jest and uploaded to [Codecov](https://codecov.io). The `jest.config.js` at the repository root defines coverage thresholds. PRs that drop coverage below thresholds will fail.

### Test Configuration Files

| File | Purpose |
|------|---------|
| `jest.config.js` | Root Jest config (coverage, retry, projects) |
| `e2e/playwright.config.ts` | Playwright config (browsers, retries, reporters) |
| `CONTRIBUTING.md` | Developer testing workflow guide |

### Branch Protection

The `main` branch requires these status checks:

- `Unit Tests (Node 18)` — must pass
- `Unit Tests (Node 20)` — must pass
- `Integration Tests` — must pass
- `E2E Tests (Critical)` — must pass

Configure via GitHub repository settings:

```bash
# Via GitHub CLI
gh api repos/{owner}/{repo}/branches/main/protection -X PUT \
  -F 'required_status_checks[strict]=true' \
  -F 'required_status_checks[contexts][]=Unit Tests (Node 18)' \
  -F 'required_status_checks[contexts][]=Unit Tests (Node 20)' \
  -F 'required_status_checks[contexts][]=Integration Tests' \
  -F 'required_status_checks[contexts][]=E2E Tests (Critical)' \
  -F 'required_pull_request_reviews[required_approving_review_count]=1' \
  -F 'enforce_admins=true'
```

### GitHub Actions Secrets (Testing)

Additional secrets required for test reporting:

```bash
# Codecov token (get from codecov.io after connecting repo)
gh secret set CODECOV_TOKEN --body "<codecov-upload-token>"
```

### Test Troubleshooting

**Unit tests failing in CI but passing locally:**
1. Check Node.js version matches the matrix (18 or 20)
2. Verify `CI=true` is set (enables retry logic)
3. Check for timezone-dependent or date-dependent tests
4. Run with `--maxWorkers=4` locally to simulate CI parallelism

**Integration tests: database connection refused:**
1. PostgreSQL service container starts automatically in the workflow
2. Verify `DATABASE_URL` matches service config: `postgresql://test_user:test_password@localhost:5432/qualisys_test`
3. Check migrations ran successfully before tests

**E2E tests timing out:**
1. E2E critical tests have a 5-minute timeout
2. Check if the application is starting (Playwright `webServer` config)
3. Verify Chromium installed correctly: `npx playwright install --with-deps chromium`
4. Review screenshots/videos in the `playwright-report` artifact

**Flaky test detected:**
1. Check retry count in test output (shows "retry 1/3" etc.)
2. Open an issue tagged `flaky-test` with the test path
3. Common causes: timing issues, shared state, external dependencies
4. Fix the root cause — do not increase retry count

**Coverage below threshold:**
1. Run `npm test -- --coverage` locally to see the report
2. Check which files are below threshold: `coverage/lcov-report/index.html`
3. Add tests for uncovered code paths
4. If new file added without tests, either add tests or exclude from coverage in `jest.config.js`
