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
│   └── rds/
│       ├── main.tf             # RDS instance, KMS, Enhanced Monitoring
│       ├── parameter-group.tf  # Custom PostgreSQL 15 parameter group
│       ├── secrets.tf          # Secrets Manager secrets, IAM policy
│       ├── variables.tf        # RDS-specific variables
│       └── outputs.tf          # DB endpoint, secret ARN for downstream
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
│   └── aws-load-balancer-controller/
│       └── values.yaml         # Helm values for AWS ALB controller
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
