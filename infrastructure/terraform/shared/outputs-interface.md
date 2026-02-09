# Terraform Outputs Interface Contract

This document defines the **unified output interface** that both the AWS and Azure Terraform root modules must produce. CI/CD workflows, Kubernetes manifests, and application configuration consume these outputs. Both roots must expose equivalent values so that downstream tooling works identically regardless of cloud provider.

---

## Required Outputs by Category

### 1. Kubernetes Cluster

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| `cluster_name` | `eks/cluster_name` | `aks/cluster_name` | `string` | Name of the Kubernetes cluster |
| `cluster_endpoint` | `eks/cluster_endpoint` | `aks/cluster_endpoint` | `string` | API server endpoint URL |
| `cluster_ca_certificate` | `eks/cluster_certificate_authority` | `aks/cluster_ca_certificate` | `string` (sensitive) | Base64-encoded CA certificate |

**AWS-only:** `cluster_oidc_provider_arn`, `cluster_oidc_provider_url`, `eks_cluster_role_arn`, `eks_node_role_arn`, `cluster_autoscaler_role_arn`, `alb_controller_role_arn`, `general_node_group_name`, `playwright_node_group_name`, `cluster_log_group_name`

**Azure-only:** `kube_config_raw`

---

### 2. Database (PostgreSQL)

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| `db_endpoint` / `postgresql_fqdn` | `rds/db_endpoint` | `postgresql/fqdn` | `string` | Database connection hostname (+ port for AWS) |
| `db_port` / `redis_port` | `rds/db_port` | n/a (default 5432) | `number` | Database connection port |

**AWS-only:** `db_instance_id`, `db_address`, `db_name`, `db_engine_version_actual`, `db_kms_key_arn`, `db_master_secret_arn`, `db_connection_secret_arn`, `db_secret_read_policy_arn`, `db_parameter_group_name`, `db_monitoring_role_arn`

**Azure-only:** `postgresql_server_id`

---

### 3. Cache (Redis)

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| `redis_hostname` / `redis_configuration_endpoint` | `elasticache/redis_configuration_endpoint` | `redis/hostname` | `string` | Redis connection hostname |
| `redis_port` | `elasticache/redis_port` (6379) | `redis/ssl_port` (6380) | `number` | Redis connection port |

**AWS-only:** `redis_replication_group_id`, `redis_engine_version_actual`, `redis_kms_key_arn`, `redis_connection_secret_arn`, `redis_secret_read_policy_arn`, `redis_parameter_group_name`

---

### 4. Container Registry

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| `registry_url` | `ecr/ecr_repository_urls` | `acr/login_server` | `string` / `map` | Container registry login server or repository URL(s) |

**AWS-only:** `ecr_repository_arns`, `ecr_registry_id`, `ecr_api_repository_url`, `ecr_web_repository_url`, `ecr_playwright_repository_url`

**Azure-only:** `acr_id`

---

### 5. Secret Management

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| secret store URI/ARN | `secrets/*_secret_arn` | `keyvault/key_vault_uri` | `string` | URI or ARN of the secret store |

**AWS-only:** `database_secret_arn`, `redis_secret_arn`, `jwt_secret_arn`, `openai_secret_arn`, `anthropic_secret_arn`, `oauth_google_secret_arn`, `email_sendgrid_secret_arn`, `secrets_kms_key_arn`, `secrets_read_infra_policy_arn`, `secrets_read_llm_policy_arn`, `secrets_read_integrations_policy_arn`, `external_secrets_role_arn`, `external_secrets_policy_arn`, `db_rotation_lambda_arn`, `secrets_alerts_topic_arn`

**Azure-only:** `key_vault_id`

---

### 6. Networking

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| VPC/VNet ID | `vpc/vpc_id` | `vnet/vnet_id` | `string` | Virtual network identifier |
| Cluster subnet(s) | `vpc/private_subnet_ids` | `vnet/aks_subnet_id` | `list`/`string` | Subnet(s) for K8s nodes |

**AWS-only:** `vpc_cidr_block`, `public_subnet_ids`, `database_subnet_ids`, `db_subnet_group_name`, `elasticache_subnet_group_name`, `alb_security_group_id`, `k8s_nodes_security_group_id`, `rds_security_group_id`, `elasticache_security_group_id`, `nat_gateway_public_ips`, `flow_log_group_name`

**Azure-only:** `resource_group_name`, `resource_group_id`

---

### 7. IAM / Identity

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| CI/CD role | `iam/cicd_role_arn` | `identity/cicd_identity_*` | `string` | Identity used by CI/CD pipelines |
| DevOps admin role | `iam/devops_admin_role_arn` | `identity/devops_group_id` | `string` | Identity for DevOps administrators |

**AWS-only:** `developer_role_arn`, `rds_service_role_arn`, `elasticache_service_role_arn`, `ecr_service_role_arn`, `cloudtrail_bucket_name`, `budget_sns_topic_arn`

**Azure-only:** `external_secrets_identity_id`, `external_secrets_identity_client_id`, `app_workload_identity_id`, `app_workload_identity_client_id`, `devops_group_id`, `developers_group_id`, `cicd_group_id`

---

### 8. Monitoring

| Output Name | AWS Source | Azure Source | Type | Description |
|---|---|---|---|---|
| Log destination | (CloudWatch log groups) | `monitoring/log_analytics_workspace_id` | `string` | Central logging destination |

---

## CI/CD Consumption Pattern

CI/CD workflows do **not** consume Terraform outputs directly. Instead:

1. **Container Registry URL** — stored as GitHub secret (`ECR_REGISTRY` for AWS, `ACR_REGISTRY_NAME` for Azure)
2. **Cluster Access** — AWS: `KUBECONFIG_BASE64` secret; Azure: `AKS_CLUSTER_NAME` + `AKS_RESOURCE_GROUP` secrets (uses `az aks get-credentials`)
3. **Cloud Selection** — `CLOUD_PROVIDER` repository variable (`aws` or `azure`)

The reusable CI/CD workflows (`.github/workflows/reusable-build.yml`, `reusable-deploy.yml`) use `if: vars.CLOUD_PROVIDER == 'aws'` / `if: vars.CLOUD_PROVIDER == 'azure'` guards to select the appropriate authentication and deployment steps.

## Kubernetes Consumption Pattern

Kubernetes manifests consume secrets via the **ExternalSecrets Operator**:
- **AWS:** `ClusterSecretStore` with `aws.SecretsManager` provider, authenticated via IRSA
- **Azure:** `ClusterSecretStore` with `azurekv` provider, authenticated via Workload Identity Federation

Both patterns produce identical Kubernetes `Secret` objects, so application pods are cloud-agnostic.

---

## Adding a New Secret

When a new application secret is needed:

1. **AWS:** Add to `infrastructure/terraform/aws/secrets/` and create ExternalSecret in `infrastructure/kubernetes/aws/external-secrets/`
2. **Azure:** Add to `infrastructure/terraform/azure/modules/keyvault/` and create ExternalSecret in `infrastructure/kubernetes/azure/external-secrets/`
3. **Shared:** Ensure both ExternalSecrets produce the same Kubernetes Secret name and key names
4. **Update this document** with the new output mapping
