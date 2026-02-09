# Story 0.20: Log Aggregation (ELK or CloudWatch)

Status: ready-for-dev

## Story

As a **Developer**,
I want **centralized log aggregation**,
so that **I can debug issues across distributed services**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Log aggregation system deployed (CloudWatch Logs or Azure Monitor Logs) | Log groups/workspaces exist for application |
| AC2 | API logs shipped to central system (request/response, errors) | Search logs for API requests returns results |
| AC3 | Worker logs shipped (background jobs, AI agent pipeline) | Search logs for worker processes returns results |
| AC4 | Kubernetes system logs collected (kubelet, kube-proxy) | Search logs for K8s events returns results |
| AC5 | Logs structured in JSON format | Log entries parse as valid JSON |
| AC6 | Logs include required fields: timestamp, level, message, trace_id, tenant_id | Sample log entry contains all fields |
| AC7 | Log retention: 30 days staging, 90 days production | Verify retention policy settings |
| AC8 | Log search interface accessible (CloudWatch Console / Azure Log Analytics) | Team can search logs with IAM/RBAC access |
| AC9 | Log-based alert: Error rate spike (>10 errors/min) | Alert fires when threshold exceeded |
| AC10 | Log-based alert: 5xx response rate >5% | Alert fires when threshold exceeded |
| AC11 | PII redaction enabled (email, names masked in logs) | Search for PII shows masked values |
| AC12 | Cross-service trace correlation via trace_id | Filter by trace_id shows related logs across services |

## Tasks / Subtasks

- [ ] **Task 1: Log Groups / Workspace Setup** (AC: 1, 7)
  - [ ] 1.1 Create log group (CloudWatch) or workspace (Azure Monitor): /qualisys/staging/api
  - [ ] 1.2 Create log group (CloudWatch) or workspace (Azure Monitor): /qualisys/staging/worker
  - [ ] 1.3 Create log group (CloudWatch) or workspace (Azure Monitor): /qualisys/production/api
  - [ ] 1.4 Create log group (CloudWatch) or workspace (Azure Monitor): /qualisys/production/worker
  - [ ] 1.5 Configure retention: 30 days staging, 90 days production
  - [ ] 1.6 Set up log group encryption (KMS on AWS, CMK on Azure)

- [ ] **Task 2: Fluent Bit DaemonSet Deployment** (AC: 2, 3, 4)
  - [ ] 2.1 Deploy Fluent Bit as DaemonSet in monitoring namespace
  - [ ] 2.2 Configure Fluent Bit to collect container logs
  - [ ] 2.3 Configure Fluent Bit to ship to CloudWatch Logs (AWS) or Azure Monitor (Azure)
  - [ ] 2.4 Set up IRSA (AWS) or Workload Identity (Azure) for Fluent Bit
  - [ ] 2.5 Configure multiline log parsing for stack traces
  - [ ] 2.6 Verify logs appearing in CloudWatch

- [ ] **Task 3: Structured Logging Implementation** (AC: 5, 6, 12)
  - [ ] 3.1 Implement JSON logger utility (Winston/Pino)
  - [ ] 3.2 Add required fields: timestamp, level, message
  - [ ] 3.3 Add trace_id correlation (from X-Request-ID header)
  - [ ] 3.4 Add tenant_id context to all log entries
  - [ ] 3.5 Create logging middleware for HTTP requests
  - [ ] 3.6 Document logging standards and usage

- [ ] **Task 4: PII Redaction** (AC: 11)
  - [ ] 4.1 Create PII redaction filter for Fluent Bit
  - [ ] 4.2 Configure email masking (user@***.com)
  - [ ] 4.3 Configure name masking (John D***)
  - [ ] 4.4 Test redaction with sample PII data
  - [ ] 4.5 Document PII handling in logs

- [ ] **Task 5: Log-Based Alerts** (AC: 9, 10)
  - [ ] 5.1 Create metric filter (CloudWatch) or alert rule (Azure Monitor) for error count
  - [ ] 5.2 Create alarm/alert for >10 errors/min
  - [ ] 5.3 Create metric filter/alert rule for 5xx responses
  - [ ] 5.4 Create alarm/alert for 5xx rate >5%
  - [ ] 5.5 Configure alarm notifications (SNS on AWS, Action Groups on Azure)
  - [ ] 5.6 Connect SNS to Slack webhook

- [ ] **Task 6: Access and Documentation** (AC: 8)
  - [ ] 6.1 Configure IAM policy (AWS) or RBAC role (Azure) for log access
  - [ ] 6.2 Create saved queries (CloudWatch Insights / KQL in Azure)
  - [ ] 6.3 Document common log search patterns
  - [ ] 6.4 Create runbook for log investigation
  - [ ] 6.5 Verify team members can access logs

## Dev Notes

### Architecture Alignment

This story implements observability infrastructure per architecture requirements:

- **NFR-OBS1**: Centralized logging with PII redaction
- **NFR-OBS2**: Correlation IDs for distributed tracing
- **NFR-R4**: Error detection for 99.5% uptime target

### Technical Constraints

- **Tool Choice**: AWS CloudWatch Logs / Azure Monitor Logs (managed, simpler than ELK for MVP)
- **Log Shipper**: Fluent Bit (lightweight, Kubernetes-native)
- **Retention**: 30 days staging, 90 days production
- **Format**: JSON structured logs with standard fields

### CloudWatch Log Groups (Terraform)

> **Multi-Cloud Note**: The Terraform and YAML examples below show the AWS variant
> (CloudWatch Logs, KMS, IRSA, SNS). Azure uses Azure Monitor Log Analytics workspaces,
> Customer-Managed Keys, Workload Identity, and Action Groups respectively.
> The Fluent Bit DaemonSet is cloud-agnostic; only the OUTPUT plugin differs.

```hcl
# modules/logging/main.tf

resource "aws_cloudwatch_log_group" "api_staging" {
  name              = "/qualisys/staging/api"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.logs.arn

  tags = {
    Environment = "staging"
    Service     = "api"
  }
}

resource "aws_cloudwatch_log_group" "api_production" {
  name              = "/qualisys/production/api"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn

  tags = {
    Environment = "production"
    Service     = "api"
  }
}

resource "aws_cloudwatch_log_group" "worker_staging" {
  name              = "/qualisys/staging/worker"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_cloudwatch_log_group" "worker_production" {
  name              = "/qualisys/production/worker"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_kms_key" "logs" {
  description             = "KMS key for CloudWatch Logs encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "Enable IAM User Permissions"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "Allow CloudWatch Logs"
        Effect    = "Allow"
        Principal = { Service = "logs.${data.aws_region.current.name}.amazonaws.com" }
        Action    = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*"]
        Resource  = "*"
      }
    ]
  })
}
```

### Fluent Bit DaemonSet

```yaml
# k8s/logging/fluent-bit.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: monitoring
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Daemon        off
        Parsers_File  parsers.conf
        HTTP_Server   On
        HTTP_Listen   0.0.0.0
        HTTP_Port     2020

    [INPUT]
        Name              tail
        Tag               kube.*
        Path              /var/log/containers/*.log
        Parser            docker
        DB                /var/log/flb_kube.db
        Mem_Buf_Limit     5MB
        Skip_Long_Lines   On
        Refresh_Interval  10

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
        Merge_Log           On
        Keep_Log            Off
        K8S-Logging.Parser  On
        K8S-Logging.Exclude On

    [FILTER]
        Name          modify
        Match         kube.*
        Rename        log message
        Add           service qualisys

    # PII Redaction Filter
    [FILTER]
        Name          lua
        Match         *
        script        /fluent-bit/scripts/pii-redact.lua
        call          redact_pii

    [OUTPUT]
        Name                cloudwatch_logs
        Match               kube.var.log.containers.qualisys-api*
        region              ${AWS_REGION}
        log_group_name      /qualisys/${ENVIRONMENT}/api
        log_stream_prefix   ${POD_NAME}-
        auto_create_group   false

    [OUTPUT]
        Name                cloudwatch_logs
        Match               kube.var.log.containers.qualisys-worker*
        region              ${AWS_REGION}
        log_group_name      /qualisys/${ENVIRONMENT}/worker
        log_stream_prefix   ${POD_NAME}-
        auto_create_group   false

  parsers.conf: |
    [PARSER]
        Name        docker
        Format      json
        Time_Key    time
        Time_Format %Y-%m-%dT%H:%M:%S.%L
        Time_Keep   On

    [PARSER]
        Name        json
        Format      json
        Time_Key    timestamp
        Time_Format %Y-%m-%dT%H:%M:%S.%LZ

  pii-redact.lua: |
    function redact_pii(tag, timestamp, record)
      -- Redact email addresses
      if record["message"] then
        record["message"] = string.gsub(record["message"],
          "([%w%.%-]+)@([%w%.%-]+%.%w+)",
          "%1@***.***")
      end

      -- Redact names (simple pattern - improve as needed)
      if record["user_name"] then
        local name = record["user_name"]
        if #name > 3 then
          record["user_name"] = string.sub(name, 1, 1) .. string.rep("*", #name - 1)
        end
      end

      return 2, timestamp, record
    end
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
  namespace: monitoring
  labels:
    app: fluent-bit
spec:
  selector:
    matchLabels:
      app: fluent-bit
  template:
    metadata:
      labels:
        app: fluent-bit
    spec:
      serviceAccountName: fluent-bit
      containers:
        - name: fluent-bit
          image: amazon/aws-for-fluent-bit:2.31.12  # AWS; Azure uses fluent/fluent-bit:latest
          env:
            - name: AWS_REGION
              value: us-east-1
            - name: ENVIRONMENT
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          volumeMounts:
            - name: varlog
              mountPath: /var/log
            - name: config
              mountPath: /fluent-bit/etc/
            - name: scripts
              mountPath: /fluent-bit/scripts/
          resources:
            requests:
              memory: 64Mi
              cpu: 50m
            limits:
              memory: 128Mi
              cpu: 100m
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
        - name: config
          configMap:
            name: fluent-bit-config
        - name: scripts
          configMap:
            name: fluent-bit-config
            items:
              - key: pii-redact.lua
                path: pii-redact.lua
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: fluent-bit
  namespace: monitoring
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/fluent-bit-cloudwatch-role  # AWS; Azure uses azure.workload.identity/client-id
```

### IRSA Policy for Fluent Bit

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": [
        "arn:aws:logs:us-east-1:ACCOUNT_ID:log-group:/qualisys/*"
      ]
    }
  ]
}
```

### Structured Logger (TypeScript)

```typescript
// src/logger/index.ts
import pino from 'pino';
import { v4 as uuidv4 } from 'uuid';

interface LogContext {
  trace_id?: string;
  tenant_id?: string;
  user_id?: string;
  [key: string]: unknown;
}

const baseLogger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
  timestamp: () => `,"timestamp":"${new Date().toISOString()}"`,
  base: {
    service: 'qualisys-api',
    environment: process.env.NODE_ENV,
  },
});

class Logger {
  private context: LogContext = {};

  setContext(ctx: LogContext) {
    this.context = { ...this.context, ...ctx };
  }

  setTraceId(traceId: string) {
    this.context.trace_id = traceId;
  }

  setTenantId(tenantId: string) {
    this.context.tenant_id = tenantId;
  }

  private log(level: string, message: string, data?: object) {
    const logEntry = {
      ...this.context,
      ...data,
      message,
    };

    switch (level) {
      case 'debug':
        baseLogger.debug(logEntry);
        break;
      case 'info':
        baseLogger.info(logEntry);
        break;
      case 'warn':
        baseLogger.warn(logEntry);
        break;
      case 'error':
        baseLogger.error(logEntry);
        break;
    }
  }

  debug(message: string, data?: object) {
    this.log('debug', message, data);
  }

  info(message: string, data?: object) {
    this.log('info', message, data);
  }

  warn(message: string, data?: object) {
    this.log('warn', message, data);
  }

  error(message: string, error?: Error, data?: object) {
    this.log('error', message, {
      ...data,
      error: error ? {
        name: error.name,
        message: error.message,
        stack: error.stack,
      } : undefined,
    });
  }
}

export const logger = new Logger();

// Express middleware
export function loggingMiddleware(req, res, next) {
  const traceId = req.headers['x-request-id'] || uuidv4();
  const tenantId = req.headers['x-tenant-id'] || 'unknown';

  req.traceId = traceId;
  res.setHeader('X-Request-ID', traceId);

  logger.setTraceId(traceId);
  logger.setTenantId(tenantId);

  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    logger.info('HTTP Request', {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: duration,
      user_agent: req.headers['user-agent'],
    });
  });

  next();
}
```

### CloudWatch Metric Filters and Alarms

```hcl
# modules/logging/alerts.tf

# Metric filter for error count
resource "aws_cloudwatch_log_metric_filter" "error_count" {
  name           = "qualisys-error-count"
  pattern        = "{ $.level = \"error\" }"
  log_group_name = aws_cloudwatch_log_group.api_production.name

  metric_transformation {
    name      = "ErrorCount"
    namespace = "QUALISYS/Application"
    value     = "1"
  }
}

# Alarm for error rate spike (AC9)
resource "aws_cloudwatch_metric_alarm" "error_rate_spike" {
  alarm_name          = "qualisys-error-rate-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ErrorCount"
  namespace           = "QUALISYS/Application"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Error rate exceeds 10 errors per minute"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Severity = "critical"
  }
}

# Metric filter for 5xx responses
resource "aws_cloudwatch_log_metric_filter" "http_5xx" {
  name           = "qualisys-http-5xx"
  pattern        = "{ $.status >= 500 }"
  log_group_name = aws_cloudwatch_log_group.api_production.name

  metric_transformation {
    name      = "5xxCount"
    namespace = "QUALISYS/Application"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "http_total" {
  name           = "qualisys-http-total"
  pattern        = "{ $.status = * }"
  log_group_name = aws_cloudwatch_log_group.api_production.name

  metric_transformation {
    name      = "RequestCount"
    namespace = "QUALISYS/Application"
    value     = "1"
  }
}

# Alarm for 5xx rate >5% (AC10)
resource "aws_cloudwatch_metric_alarm" "high_5xx_rate" {
  alarm_name          = "qualisys-high-5xx-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  threshold           = 5

  metric_query {
    id          = "error_rate"
    expression  = "5xx / total * 100"
    label       = "5xx Error Rate"
    return_data = true
  }

  metric_query {
    id = "5xx"
    metric {
      metric_name = "5xxCount"
      namespace   = "QUALISYS/Application"
      period      = 60
      stat        = "Sum"
    }
  }

  metric_query {
    id = "total"
    metric {
      metric_name = "RequestCount"
      namespace   = "QUALISYS/Application"
      period      = 60
      stat        = "Sum"
    }
  }

  alarm_description = "5xx error rate exceeds 5%"
  alarm_actions     = [aws_sns_topic.alerts.arn]
}

# SNS topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "qualisys-alerts"
}

# SNS subscription to Slack (via Lambda or AWS Chatbot)
resource "aws_sns_topic_subscription" "slack" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "https"
  endpoint  = var.slack_webhook_url
}
```

### CloudWatch Logs Insights Saved Queries

```sql
-- Find all errors in last hour
fields @timestamp, @message, trace_id, tenant_id
| filter level = "error"
| sort @timestamp desc
| limit 100

-- Find all requests for a specific trace_id
fields @timestamp, @message, level
| filter trace_id = "abc-123-def"
| sort @timestamp asc

-- Find requests with latency > 500ms
fields @timestamp, method, path, duration_ms
| filter duration_ms > 500
| sort duration_ms desc
| limit 50

-- Count errors by tenant
fields tenant_id
| filter level = "error"
| stats count() as error_count by tenant_id
| sort error_count desc

-- Find 5xx responses
fields @timestamp, method, path, status, trace_id
| filter status >= 500
| sort @timestamp desc
| limit 100
```

### Project Structure Notes

```
/
├── terraform/
│   └── modules/
│       └── logging/
│           ├── main.tf           # CloudWatch log groups
│           ├── alerts.tf         # Metric filters and alarms
│           └── variables.tf
├── k8s/
│   └── logging/
│       ├── fluent-bit.yaml       # Fluent Bit DaemonSet
│       └── serviceaccount.yaml   # IRSA service account
├── src/
│   └── logger/
│       └── index.ts              # Structured logger utility
└── docs/
    └── logging/
        ├── README.md             # Logging documentation
        └── queries.md            # Common CloudWatch queries
```

### Dependencies

- **Story 0.3** (Kubernetes Cluster) - REQUIRED: Monitoring namespace
- **Story 0.1** (IAM Setup) - REQUIRED: IAM role (AWS) or Workload Identity (Azure) for Fluent Bit
- **Story 0.7** (Secret Management) - OPTIONAL: Slack webhook URL
- Outputs used by:
  - Epic 1-5: Centralized logging for all services
  - Story 0.19: Metrics correlation with logs

### Security Considerations

1. **Threat: PII exposure in logs** → Fluent Bit PII redaction filter
2. **Threat: Unauthorized log access** → IAM/RBAC policies restrict access
3. **Threat: Log tampering** → Log service immutable, KMS/CMK encryption
4. **Threat: Log data exfiltration** → VPC endpoints (AWS) / Private Link (Azure) for log service

### Sample Log Entry

```json
{
  "timestamp": "2026-01-24T10:15:30.123Z",
  "level": "info",
  "message": "HTTP Request",
  "trace_id": "abc-123-def-456",
  "tenant_id": "tenant_acme",
  "service": "qualisys-api",
  "environment": "production",
  "method": "POST",
  "path": "/api/v1/test-cases",
  "status": 201,
  "duration_ms": 145,
  "user_agent": "Mozilla/5.0..."
}
```

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Observability]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.20]
- [Source: docs/architecture.md#Logging-Strategy]
- [Fluent Bit Documentation](https://docs.fluentbit.io/)
- [CloudWatch Logs Insights Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)

## Dev Agent Record

### Context Reference

- [docs/stories/0-20-log-aggregation-elk-or-cloudwatch.context.xml](./0-20-log-aggregation-elk-or-cloudwatch.context.xml)

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
| 2026-02-09 | PM Agent (John) | Multi-cloud course correction: generalized AWS-specific references to cloud-agnostic |
