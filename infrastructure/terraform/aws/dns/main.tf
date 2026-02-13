# DNS Configuration - AWS Route 53
# Story: 0-13 Load Balancer & Ingress Configuration
# AC: 2 - Ingress routes traffic: app.qualisys.io -> web, api.qualisys.io -> api
# AC: 3 - Staging domain configured: staging.qualisys.dev
#
# Prerequisites:
#   - NGINX Ingress Controller deployed (creates NLB)
#   - Domain names registered (qualisys.io, qualisys.dev)
#
# Apply:
#   cd infrastructure/terraform/aws
#   terraform plan -var-file="environments/dev.tfvars"
#   terraform apply -var-file="environments/dev.tfvars"
#
# Verify:
#   aws route53 list-resource-record-sets --hosted-zone-id <zone_id>
#   dig app.qualisys.io
#   dig api.qualisys.io
#   dig staging.qualisys.dev

# =====================================================
# Production Domain: qualisys.io
# =====================================================

resource "aws_route53_zone" "qualisys_io" {
  name    = "qualisys.io"
  comment = "QUALISYS production domain"

  tags = {
    Project     = "qualisys"
    Environment = "production"
    ManagedBy   = "terraform"
    Story       = "0-13"
  }
}

# Data source: NLB created by NGINX Ingress Controller
data "aws_lb" "ingress" {
  tags = {
    "kubernetes.io/service-name" = "ingress-nginx/ingress-nginx-controller"
  }
}

# app.qualisys.io -> Web frontend (production)
resource "aws_route53_record" "app_production" {
  zone_id = aws_route53_zone.qualisys_io.zone_id
  name    = "app.qualisys.io"
  type    = "A"

  alias {
    name                   = data.aws_lb.ingress.dns_name
    zone_id                = data.aws_lb.ingress.zone_id
    evaluate_target_health = true
  }
}

# api.qualisys.io -> API backend (production)
resource "aws_route53_record" "api_production" {
  zone_id = aws_route53_zone.qualisys_io.zone_id
  name    = "api.qualisys.io"
  type    = "A"

  alias {
    name                   = data.aws_lb.ingress.dns_name
    zone_id                = data.aws_lb.ingress.zone_id
    evaluate_target_health = true
  }
}

# =====================================================
# Staging Domain: qualisys.dev
# =====================================================

resource "aws_route53_zone" "qualisys_dev" {
  name    = "qualisys.dev"
  comment = "QUALISYS staging/dev domain"

  tags = {
    Project     = "qualisys"
    Environment = "staging"
    ManagedBy   = "terraform"
    Story       = "0-13"
  }
}

# staging.qualisys.dev -> Staging environment
resource "aws_route53_record" "staging" {
  zone_id = aws_route53_zone.qualisys_dev.zone_id
  name    = "staging.qualisys.dev"
  type    = "A"

  alias {
    name                   = data.aws_lb.ingress.dns_name
    zone_id                = data.aws_lb.ingress.zone_id
    evaluate_target_health = true
  }
}

# =====================================================
# Status Page Domain (optional)
# =====================================================

# status.qualisys.io -> External status page (e.g., Statuspage.io)
# Uncomment when status page is configured
# resource "aws_route53_record" "status" {
#   zone_id = aws_route53_zone.qualisys_io.zone_id
#   name    = "status.qualisys.io"
#   type    = "CNAME"
#   ttl     = 300
#   records = ["your-status-page.statuspage.io"]
# }
