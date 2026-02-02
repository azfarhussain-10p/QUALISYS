# Story 0.5: Redis Caching Layer

Status: ready-for-dev

## Story

As a **DevOps Engineer**,
I want to **provision a Redis cluster for caching and rate limiting**,
so that **the application can cache sessions, LLM responses, and enforce rate limits with high performance**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Redis 7+ ElastiCache cluster created | `aws elasticache describe-cache-clusters` shows engine version 7+ |
| AC2 | Node type: cache.t3.micro (dev), cache.r5.large (staging/prod) | Instance type matches environment configuration |
| AC3 | Cluster mode enabled with 2 shards for horizontal scaling | `aws elasticache describe-replication-groups` shows NumNodeGroups=2 |
| AC4 | Automatic failover enabled with Multi-AZ replica | `aws elasticache describe-replication-groups` shows AutomaticFailover=enabled |
| AC5 | Encryption in transit enabled (TLS) | `TransitEncryptionEnabled=true` in cluster configuration |
| AC6 | Encryption at rest enabled | `AtRestEncryptionEnabled=true` in cluster configuration |
| AC7 | Redis connection string stored in AWS Secrets Manager | `aws secretsmanager get-secret-value` retrieves Redis connection info |
| AC8 | Security group allows access only from Kubernetes private subnets | Security group inbound rules show only K8s node CIDR (10.0.10.0/24, 10.0.11.0/24) |
| AC9 | Eviction policy configured: allkeys-lru (Least Recently Used) | Parameter group shows `maxmemory-policy=allkeys-lru` |
| AC10 | Redis key namespacing strategy documented for tenant isolation | README documents key format: `tenant_id:scope:key_identifier` |

## Tasks / Subtasks

- [ ] **Task 1: ElastiCache Subnet Group Creation** (AC: 8)
  - [ ] 1.1 Create ElastiCache subnet group using database subnets from Story 0.2
  - [ ] 1.2 Verify subnet group spans both availability zones

- [ ] **Task 2: Security Group Configuration** (AC: 8)
  - [ ] 2.1 Create ElastiCache security group in VPC
  - [ ] 2.2 Add inbound rule: Allow port 6379 from K8s nodes security group only
  - [ ] 2.3 Add inbound rule: Allow port 6379 from private subnet CIDRs
  - [ ] 2.4 Verify no public access allowed

- [ ] **Task 3: Parameter Group Configuration** (AC: 9)
  - [ ] 3.1 Create custom Redis 7 parameter group: qualisys-redis7
  - [ ] 3.2 Set maxmemory-policy = allkeys-lru
  - [ ] 3.3 Set tcp-keepalive = 300 (connection health check)
  - [ ] 3.4 Set timeout = 0 (no idle timeout for persistent connections)
  - [ ] 3.5 Enable notify-keyspace-events for cache monitoring (optional)

- [ ] **Task 4: Redis Cluster Provisioning** (AC: 1, 2, 3, 4, 5, 6)
  - [ ] 4.1 Create ElastiCache Redis replication group via Terraform
  - [ ] 4.2 Configure engine version: Redis 7.0+
  - [ ] 4.3 Configure node type based on environment (t3.micro dev, r5.large prod)
  - [ ] 4.4 Enable cluster mode with 2 shards (NumNodeGroups=2)
  - [ ] 4.5 Configure 1 replica per shard (ReplicasPerNodeGroup=1)
  - [ ] 4.6 Enable Multi-AZ with automatic failover
  - [ ] 4.7 Enable at-rest encryption (default AWS KMS key)
  - [ ] 4.8 Enable in-transit encryption (TLS)
  - [ ] 4.9 Associate custom parameter group
  - [ ] 4.10 Associate subnet group

- [ ] **Task 5: Secrets Manager Integration** (AC: 7)
  - [ ] 5.1 Create Secrets Manager secret: qualisys/redis/connection
  - [ ] 5.2 Store connection info: primary endpoint, reader endpoint, port, auth token
  - [ ] 5.3 Create IAM policy allowing K8s pods to read secret (for IRSA)
  - [ ] 5.4 Document secret retrieval for application configuration

- [ ] **Task 6: Key Namespacing Documentation** (AC: 10)
  - [ ] 6.1 Document tenant isolation key format: `{tenant_id}:{scope}:{key}`
  - [ ] 6.2 Define scope categories: session, llm_cache, rate_limit, temp
  - [ ] 6.3 Document TTL recommendations per scope
  - [ ] 6.4 Add key namespacing examples to infrastructure README

- [ ] **Task 7: Validation & Testing** (AC: All)
  - [ ] 7.1 Run all acceptance criteria verification commands
  - [ ] 7.2 Test connection from K8s pod in private subnet
  - [ ] 7.3 Test TLS connection using redis-cli with --tls flag
  - [ ] 7.4 Verify connection fails from public internet
  - [ ] 7.5 Test basic Redis commands: SET, GET, DEL, EXPIRE
  - [ ] 7.6 Verify failover behavior (optional: simulate node failure)
  - [ ] 7.7 Document Redis architecture in infrastructure README

## Dev Notes

### Architecture Alignment

This story implements the Redis caching layer per the architecture document:

- **Session Management**: User sessions stored in Redis for fast retrieval
- **LLM Response Caching**: Cache AI agent responses to reduce API costs (NFR-P4)
- **Rate Limiting**: Token bucket algorithm data stored in Redis (NFR-SEC3)
- **Tenant Isolation**: Key namespacing prevents cross-tenant cache access

### Technical Constraints

- **Redis Version**: 7.0+ required for latest features and security
- **Private Subnets Only**: ElastiCache in database subnets with no public access
- **TLS Required**: All connections must use encryption in transit
- **Cluster Mode**: Required for horizontal scaling and high availability
- **Key Namespacing**: Critical for multi-tenant isolation (Red Team requirement)

### Instance Sizing

| Environment | Node Type | Memory | vCPU | Shards | Replicas | Multi-AZ |
|-------------|-----------|--------|------|--------|----------|----------|
| dev | cache.t3.micro | 0.5 GB | 2 | 1 | 0 | No |
| staging | cache.t3.small | 1.37 GB | 2 | 2 | 1 | Yes |
| production | cache.r5.large | 13.07 GB | 2 | 2 | 1 | Yes |

### Parameter Group Settings

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| maxmemory-policy | allkeys-lru | Evict least recently used keys when memory full |
| tcp-keepalive | 300 | Keep connections alive, detect dead connections |
| timeout | 0 | No idle timeout for persistent application connections |
| maxmemory | 75% of node memory | Reserve memory for Redis operations |

### Key Namespacing Strategy (Tenant Isolation)

```
# Key format: {tenant_id}:{scope}:{key_identifier}

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

**TTL Recommendations:**

| Scope | TTL | Rationale |
|-------|-----|-----------|
| session | 24 hours | User session expiry |
| llm_cache | 1-7 days | Balance freshness vs. cost savings |
| rate_limit | 1 minute | Rate limiting window |
| temp | 1 hour | Temporary processing data |

### Connection String Format

```
rediss://:${auth_token}@${primary_endpoint}:6379
```

Stored in Secrets Manager as JSON:
```json
{
  "primary_endpoint": "qualisys-redis.xxx.clustercfg.use1.cache.amazonaws.com",
  "reader_endpoint": "qualisys-redis-ro.xxx.clustercfg.use1.cache.amazonaws.com",
  "port": 6379,
  "auth_token": "stored_securely",
  "ssl_enabled": true
}
```

### Project Structure Notes

```
infrastructure/
├── terraform/
│   ├── elasticache/
│   │   ├── main.tf              # Redis cluster definition
│   │   ├── parameter-group.tf   # Custom parameter group
│   │   ├── subnet-group.tf      # ElastiCache subnet group
│   │   ├── security-group.tf    # Redis security group
│   │   ├── secrets.tf           # Secrets Manager secret
│   │   ├── variables.tf         # ElastiCache variables
│   │   └── outputs.tf           # Endpoints, secret ARN
│   └── ...
└── README.md                    # Redis architecture, key namespacing
```

### Dependencies

- **Story 0.2** (VPC & Network Configuration) - REQUIRED: database_subnet_ids, vpc_id
- Outputs used by subsequent stories:
  - Epic 1 (Foundation): Session management
  - Epic 2 (AI Agent Platform): LLM response caching
  - All Epics: Rate limiting infrastructure

### Security Considerations

From Red Team Analysis:

1. **Threat: Tenant cache isolation breach** → Mitigated by key namespacing (AC10)
2. **Threat: Data in transit exposure** → Mitigated by TLS encryption (AC5)
3. **Threat: Data at rest exposure** → Mitigated by at-rest encryption (AC6)
4. **Threat: Unauthorized access** → Mitigated by security group (AC8) + auth token

### Cost Estimate

| Environment | Configuration | Monthly Cost |
|-------------|--------------|--------------|
| dev | cache.t3.micro, 1 node | ~$12 |
| staging | cache.t3.small, 2 shards × 2 nodes | ~$48 |
| production | cache.r5.large, 2 shards × 2 nodes | ~$520 |

**Note:** Can defer Redis provisioning to Epic 2 if not needed for Sprint 0 smoke tests.

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Services-and-Modules]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Redis-Key-Namespacing]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.5]
- [Source: docs/architecture/architecture.md#Caching-Layer]

## Dev Agent Record

### Context Reference

- [docs/stories/0-5-redis-caching-layer.context.xml](./0-5-redis-caching-layer.context.xml)

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
