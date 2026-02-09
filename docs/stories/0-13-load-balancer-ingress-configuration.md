# Story 0.13: Load Balancer & Ingress Configuration

Status: ready-for-dev

## Story

As a **DevOps Engineer**,
I want **to configure load balancing and ingress with SSL termination**,
so that **external traffic reaches our applications securely with proper routing and rate limiting**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | NGINX Ingress Controller installed (cloud-agnostic) | kubectl get pods -n ingress-nginx shows running controller |
| AC2 | Ingress routes traffic: app.qualisys.io → web, api.qualisys.io → api | curl commands route to correct services |
| AC3 | Staging domain configured: staging.qualisys.dev | Browser navigates to staging URL |
| AC4 | SSL certificates provisioned via cert-manager (Let's Encrypt) | Certificates valid and auto-renewing |
| AC5 | HTTPS enforced with HTTP to HTTPS redirect | HTTP requests redirect to HTTPS (301) |
| AC6 | Health checks configured for backend services | Ingress controller routes only to healthy pods |
| AC7 | Rate limiting configured (1000 req/min per IP) | Excessive requests return 429 Too Many Requests |
| AC8 | DDoS protection enabled (AWS Shield / Azure DDoS Protection / Cloudflare) | Protection active in cloud console/Cloudflare dashboard |
| AC9 | Custom error pages configured (502, 503, 504) | Error pages show branded maintenance message |
| AC10 | Ingress annotations documented for team reference | CONTRIBUTING.md includes ingress configuration guide |

## Tasks / Subtasks

- [ ] **Task 1: Ingress Controller Installation** (AC: 1, 6)
  - [ ] 1.1 Choose ingress controller (NGINX vs ALB)
  - [ ] 1.2 Install NGINX Ingress Controller via Helm
  - [ ] 1.3 Configure controller with appropriate resources
  - [ ] 1.4 Verify controller pods running in ingress-nginx namespace
  - [ ] 1.5 Configure health check settings

- [ ] **Task 2: SSL/TLS Certificate Management** (AC: 4, 5)
  - [ ] 2.1 Install cert-manager via Helm
  - [ ] 2.2 Create ClusterIssuer for Let's Encrypt (staging + production)
  - [ ] 2.3 Configure certificate resources for domains
  - [ ] 2.4 Verify certificate issuance and auto-renewal
  - [ ] 2.5 Configure HTTPS redirect annotations

- [ ] **Task 3: DNS Configuration** (AC: 2, 3)
  - [ ] 3.1 Create DNS zone (Route 53 on AWS, Azure DNS on Azure, or external provider)
  - [ ] 3.2 Create A/CNAME records for app.qualisys.io
  - [ ] 3.3 Create A/CNAME records for api.qualisys.io
  - [ ] 3.4 Create A/CNAME records for staging.qualisys.dev
  - [ ] 3.5 Verify DNS propagation

- [ ] **Task 4: Ingress Resources** (AC: 2, 3, 5)
  - [ ] 4.1 Create Ingress resource for staging namespace
  - [ ] 4.2 Create Ingress resource for production namespace
  - [ ] 4.3 Configure path-based routing (/api → api service, / → web service)
  - [ ] 4.4 Configure host-based routing for subdomains
  - [ ] 4.5 Add SSL redirect annotations

- [ ] **Task 5: Rate Limiting & Security** (AC: 7, 8)
  - [ ] 5.1 Configure NGINX rate limiting annotations
  - [ ] 5.2 Set rate limit to 1000 req/min per IP
  - [ ] 5.3 Enable DDoS protection (AWS Shield Standard / Azure DDoS Protection)
  - [ ] 5.4 Configure Cloudflare proxy (optional, if using)
  - [ ] 5.5 Test rate limiting with load test tool

- [ ] **Task 6: Error Pages & Documentation** (AC: 9, 10)
  - [ ] 6.1 Create custom error page ConfigMap
  - [ ] 6.2 Configure default backend for error pages
  - [ ] 6.3 Style error pages with QUALISYS branding
  - [ ] 6.4 Document ingress configuration in CONTRIBUTING.md
  - [ ] 6.5 Create troubleshooting guide for common ingress issues

## Dev Notes

### Architecture Alignment

This story implements ingress configuration per the architecture document:

- **SSL Termination**: HTTPS enforced at ingress level for all traffic
- **Rate Limiting**: Protects APIs from abuse and DoS attempts
- **High Availability**: Ingress controller runs with multiple replicas
- **Routing**: Clean URL structure for API and web services

### Technical Constraints

- **SSL Required**: All production traffic must be HTTPS
- **Rate Limit**: 1000 requests/minute per IP address
- **Health Checks**: Ingress only routes to healthy backend pods
- **Redundancy**: Ingress controller must have 2+ replicas
- **Certificate Renewal**: Automatic renewal before expiration

### Ingress Controller Decision

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| NGINX Ingress | Feature-rich, battle-tested, community support | Requires separate LB | **Selected** |
| Cloud ALB Ingress | Native cloud integration (AWS ALB / Azure App GW) | Less flexible, cloud-specific | Alternative |
| Traefik | Modern, auto-discovery | Less mature ecosystem | Not selected |

### NGINX Ingress Controller Installation

```bash
# Add NGINX Ingress Helm repository
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Install NGINX Ingress Controller
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.replicaCount=2 \
  --set controller.resources.requests.cpu=100m \
  --set controller.resources.requests.memory=128Mi \
  --set controller.resources.limits.cpu=500m \
  --set controller.resources.limits.memory=256Mi \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"=nlb  # AWS only; Azure uses default LB
```

### Cert-Manager Installation

```bash
# Add cert-manager Helm repository
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Install cert-manager
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true \
  --set prometheus.enabled=false
```

### ClusterIssuer Configuration

```yaml
# kubernetes/cert-manager/cluster-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: devops@qualisys.io
    privateKeySecretRef:
      name: letsencrypt-staging-key
    solvers:
      - http01:
          ingress:
            class: nginx
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: devops@qualisys.io
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

### Production Ingress Resource

```yaml
# kubernetes/production/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: qualisys-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
    # Rate limiting
    nginx.ingress.kubernetes.io/limit-rps: "17"  # ~1000/min
    nginx.ingress.kubernetes.io/limit-connections: "10"
    # Security headers
    nginx.ingress.kubernetes.io/configuration-snippet: |
      add_header X-Frame-Options "SAMEORIGIN" always;
      add_header X-Content-Type-Options "nosniff" always;
      add_header X-XSS-Protection "1; mode=block" always;
      add_header Referrer-Policy "strict-origin-when-cross-origin" always;
spec:
  tls:
    - hosts:
        - app.qualisys.io
        - api.qualisys.io
      secretName: qualisys-production-tls
  rules:
    - host: app.qualisys.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: qualisys-web-stable
                port:
                  number: 3000
    - host: api.qualisys.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: qualisys-api-stable
                port:
                  number: 3000
```

### Staging Ingress Resource

```yaml
# kubernetes/staging/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: qualisys-staging-ingress
  namespace: staging
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/limit-rps: "17"
spec:
  tls:
    - hosts:
        - staging.qualisys.dev
      secretName: qualisys-staging-tls
  rules:
    - host: staging.qualisys.dev
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: qualisys-api
                port:
                  number: 3000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: qualisys-web
                port:
                  number: 3000
```

### Custom Error Pages

```yaml
# kubernetes/ingress-nginx/custom-error-pages.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: custom-error-pages
  namespace: ingress-nginx
data:
  502.html: |
    <!DOCTYPE html>
    <html>
    <head><title>QUALISYS - Service Temporarily Unavailable</title></head>
    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
      <h1>Service Temporarily Unavailable</h1>
      <p>We're performing maintenance. Please try again in a few minutes.</p>
      <p><a href="https://status.qualisys.io">Check system status</a></p>
    </body>
    </html>
  503.html: |
    <!DOCTYPE html>
    <html>
    <head><title>QUALISYS - Service Unavailable</title></head>
    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
      <h1>Service Unavailable</h1>
      <p>The service is temporarily unavailable. Please try again later.</p>
    </body>
    </html>
  504.html: |
    <!DOCTYPE html>
    <html>
    <head><title>QUALISYS - Gateway Timeout</title></head>
    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
      <h1>Gateway Timeout</h1>
      <p>The request took too long to process. Please try again.</p>
    </body>
    </html>
```

### DNS Configuration (Route 53 / Azure DNS)

> **Multi-Cloud Note**: The Terraform below shows the AWS Route 53 variant.
> Azure uses `azurerm_dns_zone` and `azurerm_dns_a_record` resources.
> See `infrastructure/terraform/azure/` for the Azure DNS configuration.

```hcl
# terraform/dns.tf
resource "aws_route53_zone" "qualisys_io" {
  name = "qualisys.io"
}

resource "aws_route53_record" "app" {
  zone_id = aws_route53_zone.qualisys_io.zone_id
  name    = "app.qualisys.io"
  type    = "A"
  alias {
    name                   = data.aws_lb.ingress.dns_name
    zone_id                = data.aws_lb.ingress.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.qualisys_io.zone_id
  name    = "api.qualisys.io"
  type    = "A"
  alias {
    name                   = data.aws_lb.ingress.dns_name
    zone_id                = data.aws_lb.ingress.zone_id
    evaluate_target_health = true
  }
}
```

### Rate Limiting Test

```bash
# Test rate limiting with hey (HTTP load generator)
hey -n 2000 -c 50 -q 50 https://api.qualisys.io/health

# Expected: After ~1000 requests/min from same IP, should see 429 responses
# Check for 429 Too Many Requests in output
```

### Project Structure Notes

```
/
├── kubernetes/
│   ├── ingress-nginx/
│   │   ├── values.yaml              # Helm values for NGINX Ingress
│   │   └── custom-error-pages.yaml  # Custom error page ConfigMap
│   ├── cert-manager/
│   │   └── cluster-issuer.yaml      # Let's Encrypt ClusterIssuers
│   ├── staging/
│   │   └── ingress.yaml             # Staging ingress resource
│   └── production/
│       └── ingress.yaml             # Production ingress resource
├── terraform/
│   └── dns.tf                       # Route 53 DNS configuration
└── CONTRIBUTING.md                  # Updated with ingress documentation
```

### Dependencies

- **Story 0.2** (VPC & Network) - REQUIRED: Public subnets for load balancer
- **Story 0.3** (Kubernetes Cluster) - REQUIRED: Kubernetes cluster (EKS/AKS) to deploy ingress
- Outputs used by subsequent stories:
  - Story 0.11 (Staging Deployment): Staging ingress routes traffic
  - Story 0.12 (Production Deployment): Production ingress routes traffic
  - Story 0.19 (Monitoring): Ingress metrics exposed to Prometheus

### Security Considerations

1. **Threat: SSL stripping** → HTTPS redirect enforced, HSTS headers
2. **Threat: DoS/DDoS** → Rate limiting + DDoS protection (AWS Shield / Azure DDoS)
3. **Threat: Injection via headers** → Security headers configured
4. **Threat: Certificate expiration** → cert-manager auto-renewal
5. **Threat: Exposed internal services** → Only specified hosts/paths routed

### Monitoring Integration

```yaml
# Ingress controller metrics
# Exposed at :10254/metrics for Prometheus scraping
# Key metrics:
# - nginx_ingress_controller_requests_total
# - nginx_ingress_controller_request_duration_seconds
# - nginx_ingress_controller_response_size_bytes
# - nginx_ingress_controller_ssl_certificate_expiry_time_seconds
```

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Services-and-Modules]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Security]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.13]
- [Source: docs/architecture/architecture.md#Networking]

## Dev Agent Record

### Context Reference

- [docs/stories/0-13-load-balancer-ingress-configuration.context.xml](./0-13-load-balancer-ingress-configuration.context.xml)

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
| 2026-02-09 | PM Agent (John) | Multi-cloud course correction: generalized AWS-specific references to cloud-agnostic |
