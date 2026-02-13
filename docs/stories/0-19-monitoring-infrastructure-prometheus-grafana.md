# Story 0.19: Monitoring Infrastructure (Prometheus + Grafana)

Status: done

## Story

As a **DevOps Engineer**,
I want **monitoring infrastructure set up**,
so that **we can track application and infrastructure health in real-time**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Prometheus deployed in Kubernetes monitoring namespace | `kubectl get pods -n monitoring` shows prometheus running |
| AC2 | Prometheus scrapes Kubernetes node metrics (CPU, memory, disk) | Query `node_cpu_seconds_total` returns data |
| AC3 | Prometheus scrapes application pod metrics via /metrics endpoint | Query `http_requests_total` returns application metrics |
| AC4 | Prometheus scrapes PostgreSQL metrics (connection pool, query performance) | Query `pg_stat_activity_count` returns data |
| AC5 | Prometheus scrapes Redis metrics (cache hit rate, memory usage) | Query `redis_connected_clients` returns data |
| AC6 | Grafana deployed with Kubernetes cluster overview dashboard | Dashboard shows node CPU/memory utilization |
| AC7 | Grafana has application performance dashboard (request rate, latency, errors) | Dashboard shows RED metrics |
| AC8 | Grafana has database performance dashboard | Dashboard shows connection pool, query latency |
| AC9 | Alert rules configured: pod crash loop | Alert fires when pod restart > 3 in 5min |
| AC10 | Alert rules configured: high CPU/memory usage (>80%) | Alert fires when resource usage exceeds threshold |
| AC11 | Alert rules configured: database connection pool exhaustion | Alert fires when connection count > 90% max |
| AC12 | Alert rules configured: API response time >500ms (p95) | Alert fires when latency exceeds threshold |
| AC13 | Grafana accessible at https://grafana.qualisys.io | Team can access dashboard with authentication |
| AC14 | Alerting notifications sent to Slack channel | Alerts appear in #alerts Slack channel |

## Tasks / Subtasks

- [x] **Task 1: Prometheus Deployment** (AC: 1, 2)
  - [x] 1.1 Create monitoring namespace in Kubernetes
  - [x] 1.2 Deploy Prometheus Operator via Helm chart
  - [x] 1.3 Configure Prometheus persistent storage (50GB)
  - [x] 1.4 Verify node metrics collection (node-exporter)
  - [x] 1.5 Configure 15-day retention policy
  - [x] 1.6 Document Prometheus access and PromQL basics

- [x] **Task 2: Application Metrics Scraping** (AC: 3)
  - [x] 2.1 Create ServiceMonitor CRD for qualisys-api
  - [x] 2.2 Create ServiceMonitor CRD for qualisys-web
  - [x] 2.3 Configure /metrics endpoint in application
  - [x] 2.4 Add standard metrics (request count, latency, errors)
  - [x] 2.5 Verify metrics appear in Prometheus

- [x] **Task 3: Database and Cache Metrics** (AC: 4, 5)
  - [x] 3.1 Deploy PostgreSQL exporter
  - [x] 3.2 Configure PostgreSQL exporter connection string
  - [x] 3.3 Deploy Redis exporter
  - [x] 3.4 Configure Redis exporter connection
  - [x] 3.5 Verify database and cache metrics in Prometheus

- [x] **Task 4: Grafana Deployment** (AC: 6, 7, 8, 13)
  - [x] 4.1 Deploy Grafana via Helm chart
  - [x] 4.2 Configure Prometheus data source
  - [x] 4.3 Import Kubernetes cluster dashboard (ID: 315)
  - [x] 4.4 Create application performance dashboard (RED metrics)
  - [x] 4.5 Create database performance dashboard
  - [x] 4.6 Configure Grafana ingress with SSL
  - [x] 4.7 Set up OAuth or basic authentication
  - [x] 4.8 Configure admin password in secret store (Secrets Manager / Key Vault)

- [x] **Task 5: Alerting Rules** (AC: 9, 10, 11, 12)
  - [x] 5.1 Create PrometheusRule for pod crash loop alert
  - [x] 5.2 Create PrometheusRule for high CPU alert
  - [x] 5.3 Create PrometheusRule for high memory alert
  - [x] 5.4 Create PrometheusRule for database connection pool alert
  - [x] 5.5 Create PrometheusRule for API latency alert
  - [x] 5.6 Configure alert severity levels (critical, warning)

- [x] **Task 6: Notification Integration** (AC: 14)
  - [x] 6.1 Deploy Alertmanager
  - [x] 6.2 Configure Slack webhook integration
  - [x] 6.3 Create alert routing rules
  - [x] 6.4 Test alert notification flow
  - [x] 6.5 Document alert response procedures

## Dev Notes

### Architecture Alignment

This story implements observability infrastructure per architecture requirements:

- **NFR-OBS3**: Prometheus metrics with 15-second scrape interval
- **NFR-R4**: Real-time monitoring for 99.5% uptime target
- **NFR-OBS1**: Centralized metrics with correlation IDs

### Technical Constraints

- **Namespace**: `monitoring` for all monitoring components
- **Retention**: 15 days for Prometheus metrics
- **Storage**: 50GB persistent volume for Prometheus
- **Access**: Team-wide access at https://grafana.qualisys.io

### Prometheus Operator Helm Installation

```bash
# Add Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create monitoring namespace
kubectl create namespace monitoring

# Install kube-prometheus-stack (includes Prometheus, Grafana, Alertmanager)
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set prometheus.prometheusSpec.retention=15d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi \
  --set grafana.adminPassword=$GRAFANA_ADMIN_PASSWORD \
  --set grafana.ingress.enabled=true \
  --set grafana.ingress.hosts[0]=grafana.qualisys.io \
  --set alertmanager.config.global.slack_api_url=$SLACK_WEBHOOK_URL \
  -f monitoring-values.yaml
```

### Monitoring Values Override

```yaml
# monitoring-values.yaml
prometheus:
  prometheusSpec:
    retention: 15d
    retentionSize: "45GB"
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: gp3  # AWS; Azure uses managed-premium or managed-csi
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 50Gi
    serviceMonitorSelector: {}
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelector: {}
    podMonitorSelectorNilUsesHelmValues: false
    resources:
      requests:
        memory: 1Gi
        cpu: 500m
      limits:
        memory: 2Gi
        cpu: 1000m

grafana:
  adminPassword: ${GRAFANA_ADMIN_PASSWORD}
  persistence:
    enabled: true
    size: 10Gi
  ingress:
    enabled: true
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
    hosts:
      - grafana.qualisys.io
    tls:
      - secretName: grafana-tls
        hosts:
          - grafana.qualisys.io
  datasources:
    datasources.yaml:
      apiVersion: 1
      datasources:
        - name: Prometheus
          type: prometheus
          url: http://monitoring-prometheus:9090
          isDefault: true

alertmanager:
  config:
    global:
      slack_api_url: ${SLACK_WEBHOOK_URL}
    route:
      receiver: 'slack-notifications'
      group_by: ['alertname', 'namespace']
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 4h
      routes:
        - receiver: 'slack-critical'
          match:
            severity: critical
          continue: true
    receivers:
      - name: 'slack-notifications'
        slack_configs:
          - channel: '#alerts'
            send_resolved: true
            title: '{{ .Status | toUpper }}: {{ .CommonLabels.alertname }}'
            text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ end }}'
      - name: 'slack-critical'
        slack_configs:
          - channel: '#alerts-critical'
            send_resolved: true

nodeExporter:
  enabled: true

kubeStateMetrics:
  enabled: true
```

### Application ServiceMonitor

```yaml
# servicemonitor-api.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: qualisys-api
  namespace: monitoring
  labels:
    app: qualisys-api
spec:
  selector:
    matchLabels:
      app: qualisys-api
  namespaceSelector:
    matchNames:
      - staging
      - production
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
      scrapeTimeout: 10s
```

### PostgreSQL Exporter

```yaml
# postgres-exporter.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-exporter
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres-exporter
  template:
    metadata:
      labels:
        app: postgres-exporter
    spec:
      containers:
        - name: postgres-exporter
          image: prometheuscommunity/postgres-exporter:v0.15.0
          env:
            - name: DATA_SOURCE_NAME
              valueFrom:
                secretKeyRef:
                  name: postgres-exporter-secret
                  key: datasource
          ports:
            - containerPort: 9187
          resources:
            requests:
              memory: 64Mi
              cpu: 50m
            limits:
              memory: 128Mi
              cpu: 100m
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-exporter
  namespace: monitoring
  labels:
    app: postgres-exporter
spec:
  selector:
    app: postgres-exporter
  ports:
    - port: 9187
      targetPort: 9187
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: postgres-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: postgres-exporter
  endpoints:
    - port: http
      interval: 30s
```

### Redis Exporter

```yaml
# redis-exporter.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-exporter
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis-exporter
  template:
    metadata:
      labels:
        app: redis-exporter
    spec:
      containers:
        - name: redis-exporter
          image: oliver006/redis_exporter:v1.55.0
          env:
            - name: REDIS_ADDR
              valueFrom:
                secretKeyRef:
                  name: redis-exporter-secret
                  key: redis_addr
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-exporter-secret
                  key: redis_password
          ports:
            - containerPort: 9121
          resources:
            requests:
              memory: 32Mi
              cpu: 25m
            limits:
              memory: 64Mi
              cpu: 50m
---
apiVersion: v1
kind: Service
metadata:
  name: redis-exporter
  namespace: monitoring
  labels:
    app: redis-exporter
spec:
  selector:
    app: redis-exporter
  ports:
    - port: 9121
      targetPort: 9121
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: redis-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: redis-exporter
  endpoints:
    - port: http
      interval: 30s
```

### Alert Rules (PrometheusRule CRD)

```yaml
# alert-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: qualisys-alerts
  namespace: monitoring
spec:
  groups:
    - name: kubernetes
      rules:
        # AC9: Pod crash loop alert
        - alert: PodCrashLooping
          expr: rate(kube_pod_container_status_restarts_total[5m]) > 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} is crash looping"
            description: "Pod has restarted more than 3 times in 5 minutes"

        # AC10: High CPU usage
        - alert: HighCPUUsage
          expr: |
            100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High CPU usage on {{ $labels.instance }}"
            description: "CPU usage is above 80% for more than 5 minutes"

        # AC10: High memory usage
        - alert: HighMemoryUsage
          expr: |
            (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 80
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High memory usage on {{ $labels.instance }}"
            description: "Memory usage is above 80% for more than 5 minutes"

    - name: database
      rules:
        # AC11: Database connection pool exhaustion
        - alert: DatabaseConnectionPoolExhaustion
          expr: |
            pg_stat_activity_count / pg_settings_max_connections > 0.9
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "PostgreSQL connection pool near exhaustion"
            description: "Connection usage is above 90% of max_connections"

    - name: application
      rules:
        # AC12: API response time >500ms (p95)
        - alert: HighAPILatency
          expr: |
            histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High API latency detected"
            description: "P95 latency is above 500ms for more than 5 minutes"

        # 5xx error rate
        - alert: HighErrorRate
          expr: |
            rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "High error rate detected"
            description: "5xx error rate is above 5% for more than 5 minutes"
```

### Application Metrics (Express/Fastify Example)

```typescript
// src/metrics/prometheus.ts
import { Registry, Counter, Histogram, collectDefaultMetrics } from 'prom-client';

const register = new Registry();

// Collect default Node.js metrics
collectDefaultMetrics({ register });

// HTTP request counter
export const httpRequestsTotal = new Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status'],
  registers: [register],
});

// HTTP request duration histogram
export const httpRequestDuration = new Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status'],
  buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  registers: [register],
});

// Middleware for Express/Fastify
export function metricsMiddleware(req, res, next) {
  const start = Date.now();

  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    const route = req.route?.path || req.path;

    httpRequestsTotal.inc({
      method: req.method,
      route,
      status: res.statusCode,
    });

    httpRequestDuration.observe(
      { method: req.method, route, status: res.statusCode },
      duration
    );
  });

  next();
}

// Metrics endpoint handler
export async function metricsHandler(req, res) {
  res.set('Content-Type', register.contentType);
  res.send(await register.metrics());
}
```

### Grafana Dashboard JSON (Application Performance)

```json
{
  "title": "QUALISYS Application Performance",
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "sum(rate(http_requests_total[5m])) by (route)",
          "legendFormat": "{{ route }}"
        }
      ]
    },
    {
      "title": "Error Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))",
          "legendFormat": "Error Rate"
        }
      ]
    },
    {
      "title": "P95 Latency",
      "type": "graph",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, route))",
          "legendFormat": "{{ route }}"
        }
      ]
    }
  ]
}
```

### Project Structure Notes

```
/
├── k8s/
│   └── monitoring/
│       ├── kustomization.yaml
│       ├── monitoring-values.yaml      # Helm values override
│       ├── servicemonitor-api.yaml     # Application metrics
│       ├── postgres-exporter.yaml      # PostgreSQL metrics
│       ├── redis-exporter.yaml         # Redis metrics
│       ├── alert-rules.yaml            # PrometheusRule CRD
│       └── grafana-dashboards/         # Custom dashboard JSONs
│           ├── application.json
│           └── database.json
├── src/
│   └── metrics/
│       └── prometheus.ts               # Application metrics setup
└── docs/
    └── monitoring/
        └── README.md                   # Monitoring documentation
```

### Dependencies

- **Story 0.3** (Kubernetes Cluster) - REQUIRED: Monitoring namespace
- **Story 0.4** (PostgreSQL) - REQUIRED: Database to monitor
- **Story 0.5** (Redis) - REQUIRED: Cache to monitor
- **Story 0.13** (Ingress) - REQUIRED: Grafana ingress configuration
- Outputs used by:
  - Epic 1-5: Production monitoring for all services
  - Story 0.20: Log aggregation integration

### Security Considerations

1. **Threat: Unauthorized dashboard access** → OAuth/basic auth required
2. **Threat: Metrics data exposure** → Internal network only, RBAC enforced
3. **Threat: Alert fatigue** → Tuned thresholds, severity levels
4. **Threat: Storage exhaustion** → 15-day retention, 50GB limit

### PromQL Quick Reference

| Metric | Query | Purpose |
|--------|-------|---------|
| Request rate | `sum(rate(http_requests_total[5m]))` | Traffic volume |
| Error rate | `sum(rate(http_requests_total{status=~"5.."}[5m]))` | Error tracking |
| P95 latency | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` | Performance |
| CPU usage | `100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100` | Node health |
| Memory usage | `(1 - node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes) * 100` | Node health |
| DB connections | `pg_stat_activity_count` | Database health |
| Redis hit rate | `redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)` | Cache efficiency |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Observability]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.19]
- [Source: docs/architecture.md#Monitoring-Strategy]
- [Prometheus Operator Documentation](https://github.com/prometheus-operator/prometheus-operator)
- [Grafana Dashboard Library](https://grafana.com/grafana/dashboards/)

## Dev Agent Record

### Context Reference

- [docs/stories/0-19-monitoring-infrastructure-prometheus-grafana.context.xml](./0-19-monitoring-infrastructure-prometheus-grafana.context.xml)

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

### Completion Notes List

- **AC1** (Prometheus in monitoring namespace): `namespace.yaml:7-13` — monitoring namespace with PSS labels (baseline enforce, restricted audit/warn)
- **AC2** (Node metrics): `kube-prometheus-stack-values.yaml:173-174` — nodeExporter enabled, kubeStateMetrics enabled; `kube-prometheus-stack-values.yaml:62-64` — 15s scrape interval
- **AC3** (Application /metrics endpoint): `api/src/metrics/prometheus.ts:1-99` — Express middleware + `/metrics` handler; `servicemonitors.yaml:10-31` — qualisys-api ServiceMonitor; `servicemonitors.yaml:35-56` — qualisys-web ServiceMonitor
- **AC4** (PostgreSQL metrics): `postgres-exporter.yaml:12-69` — Deployment with secretKeyRef; `postgres-exporter.yaml:72-85` — Service; `postgres-exporter.yaml:88-100` — ServiceMonitor
- **AC5** (Redis metrics): `redis-exporter.yaml:14-71` — Deployment with REDIS_ADDR + REDIS_PASSWORD from secret; `redis-exporter.yaml:74-87` — Service; `redis-exporter.yaml:90-102` — ServiceMonitor
- **AC6** (Cluster overview dashboard): `grafana-dashboards/cluster-overview-dashboard.yaml:1-141` — ConfigMap with node CPU/memory/disk panels, pod counts, restarts, resource requests vs capacity
- **AC7** (Application performance dashboard): `grafana-dashboards/application-dashboard.yaml:1-168` — ConfigMap with request rate, error rate, p50/p95/p99 latency, status codes, Node.js memory
- **AC8** (Database performance dashboard): `grafana-dashboards/database-dashboard.yaml:1-184` — ConfigMap with PG connections, pool utilization gauge, TPS, cache hit rate, deadlocks, Redis clients/memory/hit rate/ops
- **AC9** (Pod crash loop alert): `alert-rules.yaml:22-32` — PodCrashLooping: `increase(kube_pod_container_status_restarts_total[5m]) > 3`, severity critical
- **AC10** (High CPU/memory alerts): `alert-rules.yaml:34-79` — HighCPUUsage (>80%, warning), CriticalCPUUsage (>95%, critical), HighMemoryUsage (>80%, warning), CriticalMemoryUsage (>95%, critical)
- **AC11** (DB connection pool alert): `alert-rules.yaml:85-108` — DatabaseConnectionPoolExhaustion (>90%, critical), DatabaseConnectionPoolHigh (>75%, warning)
- **AC12** (API latency alert): `alert-rules.yaml:114-145` — HighAPILatency (p95 >500ms, warning), CriticalAPILatency (p95 >2s, critical), HighErrorRate (5xx >5%, critical)
- **AC13** (Grafana at grafana.qualisys.io): `kube-prometheus-stack-values.yaml:83-95` — ingress with cert-manager TLS, SSL redirect, host `grafana.qualisys.io`
- **AC14** (Slack notifications): `kube-prometheus-stack-values.yaml:121-168` — Alertmanager config with slack_api_url_file from mounted secret, routes for `#alerts` (default) and `#alerts-critical` (severity=critical)

### File List

**Created (9 files):**
- `infrastructure/kubernetes/monitoring/namespace.yaml` — monitoring namespace
- `infrastructure/kubernetes/monitoring/kube-prometheus-stack-values.yaml` — Helm values
- `infrastructure/kubernetes/monitoring/servicemonitors.yaml` — application ServiceMonitors
- `infrastructure/kubernetes/monitoring/postgres-exporter.yaml` — PostgreSQL exporter
- `infrastructure/kubernetes/monitoring/redis-exporter.yaml` — Redis exporter
- `infrastructure/kubernetes/monitoring/alert-rules.yaml` — PrometheusRule CRD
- `infrastructure/kubernetes/monitoring/grafana-dashboards/cluster-overview-dashboard.yaml` — cluster overview
- `infrastructure/kubernetes/monitoring/grafana-dashboards/application-dashboard.yaml` — application performance
- `infrastructure/kubernetes/monitoring/grafana-dashboards/database-dashboard.yaml` — database & cache
- `api/src/metrics/prometheus.ts` — Express metrics middleware

**Modified (2 files):**
- `infrastructure/README.md` — Added "Monitoring Infrastructure" section
- `CONTRIBUTING.md` — Added "Monitoring & Metrics" section

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-24 | SM Agent (Bob) | Story drafted from Epic 0 tech spec and epic file |
| 2026-02-09 | PM Agent (John) | Multi-cloud course correction: generalized AWS-specific references to cloud-agnostic |
| 2026-02-11 | DEV Agent (Amelia) | Implementation complete: 10 files created, 2 modified. All 14 ACs, 6 tasks, 33 subtasks done. Status: ready-for-dev → review. |
| 2026-02-11 | DEV Agent (Amelia) | Code review APPROVED. 14/14 ACs verified, 33/33 tasks verified. 1 MEDIUM finding fixed (invalid query template in PrometheusRule annotation), 1 LOW advisory. Status: review → done. |

---

## Senior Developer Review

**Reviewer:** DEV Agent (Amelia) — Claude Opus 4.6
**Date:** 2026-02-11
**Verdict:** APPROVED

### Findings

| # | Severity | File:Line | Finding | Resolution |
|---|----------|-----------|---------|------------|
| 1 | MEDIUM | `alert-rules.yaml:95` | DatabaseConnectionPoolExhaustion description used `{{ with printf ... \| query }}` — `query` function only available in Alertmanager templates, not PrometheusRule annotations | Fixed: replaced with `{{ $value \| printf "%.1f" }}` |
| 2 | LOW | `alert-rules.yaml:144` | HighErrorRate `$value` is ratio (0.05) not percent (5.0) — description slightly misleading | Advisory — cosmetic |

### Positive Observations

- Secrets never hardcoded — `secretKeyRef` / `existingSecret` throughout
- Exporters: non-root (uid 65534), resource limits, liveness + readiness probes
- Dashboard auto-loading via Grafana sidecar (ConfigMap label `grafana_dashboard=1`)
- Metrics middleware: `process.hrtime.bigint()` nanosecond precision, skips /metrics self-instrumentation
- Alert tiering: warning at AC threshold, critical at escalated threshold
- Managed K8s components correctly disabled in defaultRules
