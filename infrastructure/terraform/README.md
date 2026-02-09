# QUALISYS Infrastructure — Terraform

QUALISYS supports deployment on **AWS** or **Azure** using a **Two Roots** architecture. Each customer deployment targets one cloud provider; the choice is made at build time, not runtime.

## Two Roots Architecture

```
infrastructure/terraform/
├── aws/                  # AWS root module (EKS, RDS, ElastiCache, ECR, ...)
│   ├── providers.tf      # AWS provider configuration
│   ├── backend.tf        # S3 + DynamoDB state backend
│   ├── variables.tf
│   ├── outputs.tf
│   ├── vpc/              # VPC, subnets, security groups, NAT
│   ├── eks/              # EKS cluster, node groups, IRSA
│   ├── rds/              # RDS PostgreSQL with pgvector
│   ├── elasticache/      # ElastiCache Redis cluster
│   ├── ecr/              # ECR container repositories
│   ├── secrets/          # Secrets Manager + ExternalSecrets IRSA
│   ├── iam/              # IAM roles, policies, account setup
│   ├── monitoring/       # CloudWatch, CloudTrail, Budgets
│   ├── bootstrap/        # S3 + DynamoDB for Terraform state
│   └── environments/     # Per-environment tfvars
│
├── azure/                # Azure root module (AKS, PostgreSQL, Redis, ACR, ...)
│   ├── providers.tf      # AzureRM + AzureAD providers
│   ├── backend.tf        # Azure Storage Account state backend
│   ├── main.tf           # Module composition
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── resource-group/   # Resource group + naming
│       ├── vnet/             # VNet, subnets, NSGs, NAT Gateway
│       ├── aks/              # AKS cluster, node pools, Workload Identity
│       ├── postgresql/       # PostgreSQL Flexible Server with pgvector
│       ├── redis/            # Azure Cache for Redis
│       ├── acr/              # Azure Container Registry
│       ├── keyvault/         # Azure Key Vault + application secrets
│       ├── identity/         # Azure AD groups, Managed Identities
│       └── monitoring/       # Log Analytics, Activity Log, Budgets
│
└── shared/
    └── outputs-interface.md  # Output contract between both roots
```

## AWS → Azure Service Mapping

| Concern | AWS | Azure |
|---|---|---|
| **Kubernetes** | EKS | AKS |
| **Database** | RDS PostgreSQL 15 | PostgreSQL Flexible Server 15 |
| **Cache** | ElastiCache Redis 7 | Azure Cache for Redis |
| **Container Registry** | ECR | ACR |
| **Secrets** | Secrets Manager + KMS | Key Vault |
| **Pod Auth → Secrets** | IRSA (OIDC) | Workload Identity Federation |
| **Networking** | VPC + Subnets + SGs | VNet + Subnets + NSGs |
| **State Backend** | S3 + DynamoDB | Storage Account + Table |
| **Logging** | CloudWatch + CloudTrail | Log Analytics + Activity Log |
| **Budgets** | AWS Budgets + SNS | Azure Cost Management + Action Groups |
| **IAM** | IAM Roles + Policies | Azure AD + Managed Identities |

## Quick Start

### AWS Deployment

```bash
# 1. Bootstrap state backend (one-time)
cd infrastructure/terraform/aws/bootstrap
terraform init && terraform apply

# 2. Deploy infrastructure
cd infrastructure/terraform/aws
terraform init
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

### Azure Deployment

```bash
# 1. Bootstrap state backend (one-time)
az group create --name qualisys-tfstate-rg --location eastus
az storage account create --name qualisystfstate --resource-group qualisys-tfstate-rg --sku Standard_LRS
az storage container create --name tfstate --account-name qualisystfstate
az storage table create --name tflock --account-name qualisystfstate

# 2. Deploy infrastructure
cd infrastructure/terraform/azure
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

## CI/CD Integration

The choice of cloud provider is controlled by the `CLOUD_PROVIDER` GitHub repository variable (values: `aws` or `azure`). CI/CD workflows use conditional `if:` guards to select the appropriate authentication, build, and deploy steps. See `.github/workflows/` for details.

### Required GitHub Secrets by Provider

**AWS:**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `ECR_REGISTRY`, `KUBECONFIG_BASE64`

**Azure:**
- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- `ACR_REGISTRY_NAME`, `AKS_CLUSTER_NAME`, `AKS_RESOURCE_GROUP`

**Shared:**
- `SLACK_WEBHOOK_URL` (optional, for deployment notifications)

## Kubernetes Manifests

Kubernetes manifests are organized in `infrastructure/kubernetes/`:

```
infrastructure/kubernetes/
├── shared/     # Cloud-agnostic (namespaces, RBAC, resource quotas)
├── aws/        # AWS-specific (aws-auth ConfigMap, IRSA SecretStore)
└── azure/      # Azure-specific (Workload Identity, Key Vault SecretStore)
```

Apply in order: `shared/` first, then cloud-specific directory.

## Output Interface

Both AWS and Azure roots produce outputs consumed by CI/CD and Kubernetes. See `shared/outputs-interface.md` for the full mapping and consumption patterns.
