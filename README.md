# QUALISYS

[![PR Checks](https://github.com/10pearls/qualisys/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/10pearls/qualisys/actions/workflows/pr-checks.yml)
[![codecov](https://codecov.io/gh/10pearls/qualisys/branch/main/graph/badge.svg)](https://codecov.io/gh/10pearls/qualisys)

**AI System Quality Assurance Platform**

> Revolutionizing software testing through intelligent document ingestion, Git repository codebase analysis, multi-agent AI capabilities, and self-healing test automation. QUALISYS creates a new category - "AI System Quality Assurance" - providing comprehensive testing across all AI types while addressing the unique challenges of testing in the non-deterministic AI era.

---

## 📊 Project Status

| Metric | Value |
|--------|-------|
| **Current Phase** | Phase 4: Implementation |
| **Current Epic** | Epic 1 - Foundation & Administration |
| **Track** | Enterprise BMad Method |
| **Total Stories** | 108 (100 MVP + 8 Post-MVP) |
| **Epics** | 6 (Epic 0-5 MVP, Epic 6 Post-MVP) |
| **Status** | Sprint 1 - Foundation & Administration |
| **Completed** | Epic 0 (22/22 stories) |
| **Version** | 0.1.0 (Pre-release) |
| **Last Updated** | 2026-02-12 |

---

## 🎯 Project Vision

QUALISYS is an **AI System Quality Assurance Platform** that transforms testing from a manual bottleneck into an intelligent, self-maintaining system. The platform addresses a critical market gap: companies shipping AI features lack proper testing tools for non-deterministic AI behavior.

**The Core Problem:** Software teams spend 40% of their time on manual testing activities, test automation scripts break constantly with UI changes, and test coverage gaps lead to bugs escaping to production. Traditional testing tools were built for deterministic software and cannot handle AI's non-deterministic nature.

**The Solution:** QUALISYS combines three breakthrough capabilities:
1. **Multi-Agent AI System** - 7 specialized AI agents (3 MVP + 4 Post-MVP) work in orchestrated pipelines
2. **Self-Healing Test Automation** - Automatically detects DOM changes and proposes fixes
3. **End-to-End Testing Lifecycle** - Complete coverage from requirements ingestion to executive dashboards

**The "5-Minute Value Moment":** Users upload their PRD, connect their app URL and GitHub repo, select AI agents to run, and within minutes receive generated test suites (manual checklists + automated Playwright scripts) ready to execute.

---

## 📚 Documentation

**[→ View Complete Documentation](./docs/index.md)**

### Documentation Structure

```
docs/
├── index.md                    # Documentation index (start here)
├── planning/                   # Phase 2: Planning Artifacts
│   ├── prd.md                  # Product Requirements Document (110 FRs)
│   ├── product-brief-*.md      # Product brief & market positioning
│   └── ux-design-specification.md
├── architecture/               # Phase 3: Architecture & Solutioning
│   └── architecture.md         # System architecture (3600+ lines)
├── epics/                      # Epic Definitions
│   ├── epics.md               # All epics overview
│   └── epic-0-infrastructure.md
├── tech-specs/                # Epic Technical Specifications
│   ├── tech-spec-epic-0.md    # Infrastructure tech spec
│   └── tech-spec-epic-1.md    # Foundation & Admin tech spec
├── stories/                   # Story Files
├── reports/                   # Validation & Readiness Reports
├── research/                 # Market & Competitive Research
└── improvements/             # Agent improvement research & plans
```

**Quick Links:**
- [Documentation Index](./docs/index.md) - Complete documentation overview
- [Product Requirements Document](./docs/planning/prd.md) - 110 functional requirements
- [System Architecture](./docs/architecture/architecture.md) - Technical design & risk analysis
- [Epic Overview](./docs/epics/epics.md) - All epics breakdown
- [Implementation Readiness Report](./docs/reports/implementation-readiness-report-2026-01-22.md) - Phase 3→4 validation
- [Sprint Change Proposal](./docs/sprint-change-proposal-2026-02-06.md) - Agent restructuring (8→6 agents)

---

## ✨ Key Features

### 🤖 Multi-Agent AI System
- **7 specialized AI agents** for comprehensive test generation:
  - **BAConsultant AI Agent**: Requirements analysis, gap/ambiguity detection, coverage matrix, user story creation with quality scoring (MVP)
  - **QAConsultant AI Agent**: Test strategy, manual test checklists, BDD/Gherkin scenarios, checklist-driven testing, synthetic test data, sprint readiness validation (MVP)
  - **AutomationConsultant AI Agent**: Playwright/Puppeteer/REST-Assured script generation, framework architecture, DOM crawling and discovery, automation suite management, CI/CD integration (MVP)
  - **AI Log Reader/Summarizer**: Test execution log analysis (Post-MVP)
  - **Security Scanner Orchestrator**: Security testing automation (Post-MVP)
  - **Performance/Load Agent**: Load testing and performance validation (Post-MVP)
  - **DatabaseConsultant AI Agent**: Schema validation, data integrity, ETL validation, DB performance profiling (Post-MVP)
- Intelligent orchestration and pipeline management
- User-selectable or automated agent workflows

### 📄 Intelligent Ingestion
- **Document Parsing**: Upload PRD, SRS, RFP, specification documents (PDF, MS Word, Markdown)
- **Source Code Reader**: Connect GitHub repo (read-only token), parse routes/APIs/components
- **DOM Crawler**: Playwright-based crawler to capture site map, pages, forms, dynamic flows
- Handle authentication flows (login, cookies) during crawling
- Generate embeddings and store in vector database for semantic search

### 🔄 Self-Healing Test Automation
- **Multiple selector strategies**: CSS, XPath, text anchors, accessibility labels, visual anchors
- **DOM change detection**: Store page fingerprints, on failure propose patched selectors
- **Confidence scoring**: Show confidence scores for proposed fixes
- **Approval workflow**: PM/Automation Engineer approval required before applying fixes
- **Versioned artifacts**: Audit trail of all auto-fixes with before/after comparisons
- **ML-suggested selectors**: Advanced ML-based selector optimization (Post-MVP)

### 📊 Comprehensive Dashboards
- **PM/CSM Dashboards**: Project health, test coverage %, test execution velocity, P1/P2 defect leakage, SLA compliance
- **QA Dashboards**: Current test runs, failing suites, flaky tests, environment status
- **Real-time KPIs**: Live test execution status, coverage trends, velocity metrics
- **Exportable Reports**: PDF reports for stakeholders
- **Role-based views**: Optimized interfaces for each persona

### 🔗 Enterprise Integrations
- **Issue Tracking**: Jira (bi-directional sync), GitHub Issues
- **Test Management**: TestRail, Testworthy (import/export/sync)
- **Version Control**: GitHub (PR comments, webhooks, test triggers)
- **CI/CD**: GitHub Actions, GitLab CI (deep integration)
- **ChatOps**: Slack, MS Teams (notifications, ChatOps commands)
- **Auth**: SSO (SAML/OAuth/OIDC), Keycloak, Google OAuth

---

## 🏗️ Tech Stack

### Frontend
- **Framework**: Next.js 14+ (React + TypeScript)
- **Styling**: Tailwind CSS + shadcn/ui component library
- **Charts**: Recharts for dashboards and analytics
- **Real-time**: WebSocket/SSE for live test execution updates
- **Code Splitting**: Per-persona bundles for optimal performance

### Backend
- **Primary**: Python FastAPI (async, high-performance API)
- **AI Orchestration**: LangChain for multi-agent workflows
- **Job Queue**: Celery / RQ / RabbitMQ for async task distribution
- **Optional**: Node.js/NestJS for specific integration services

### AI & ML
- **LLM Provider**: OpenAI GPT-4 (MVP), self-hosted option (Post-MVP)
- **Development**: Ollama for local LLM testing
- **Production**: vLLM for self-hosted LLM serving (Post-MVP)
- **Embeddings**: sentence-transformers for document embeddings
- **Observability**: LangFuse for LLM prompt/response tracking and cost monitoring

### Databases & Storage
- **Relational**: PostgreSQL 15+ (multi-tenant with schema-per-tenant isolation)
- **Vector**: pgvector (PostgreSQL extension) for embeddings storage
- **Cache**: Redis 7+ (cluster mode) for sessions, rate limiting, LLM response caching
- **Object Storage**: AWS S3 / MinIO for test artifacts, screenshots, videos
- **Timeseries**: Prometheus for metrics collection

### Testing & Security
- **E2E Automation**: Playwright (primary), Puppeteer (alternative)
- **Load/Performance**: k6, Locust for load testing
- **Security Scanning**: OWASP ZAP, Snyk for vulnerability detection
- **API Testing**: Postman/Newman, REST-assured
- **Code Safety**: Semgrep, Snyk, Bandit for all generated code

### Infrastructure
- **Cloud Platform**: AWS **or** Azure (build-time choice per deployment)
  - **AWS**: EKS, RDS, ElastiCache, ECR, S3, Secrets Manager, IAM, VPC
  - **Azure**: AKS, PostgreSQL Flexible Server, Azure Cache for Redis, ACR, Key Vault, Managed Identities, VNet
- **Orchestration**: Kubernetes (EKS or AKS) + Helm charts
- **CI/CD**: GitHub Actions (automated builds, tests, deployments) with `CLOUD_PROVIDER` variable
- **Secrets Management**: AWS Secrets Manager / Azure Key Vault (via ExternalSecrets Operator)
- **Monitoring**: CloudWatch + CloudTrail (AWS) / Log Analytics + Activity Log (Azure)
- **Container Registry**: AWS ECR / Azure ACR for Docker images

---

## 🎯 Target Audience

QUALISYS serves 6 distinct personas with role-optimized interfaces:

1. **Owner/Admin** - Full platform access, billing, user management, organization settings
2. **PM/CSM** (Project Manager / Customer Success Manager) - Project oversight, SLA management, reporting, dashboards
3. **QA-Manual** (Manual Test Engineer) - Execute manual test checklists, evidence capture, defect filing
4. **QA-Automation** (Automation Engineer) - Generate and execute automated tests, configure self-healing, approve fixes
5. **Dev** (Developer) - View test results, run tests on-demand, PR integration
6. **Viewer** - Read-only access to dashboards and reports

**Beachhead Market:** Software development organizations including software houses, freelance development teams, and companies with in-house application development teams.

---

## 🗺️ Roadmap & Epics

The QUALISYS MVP is organized into 6 epics with 108 total stories (100 MVP + 8 Post-MVP):

### Epic 0: Infrastructure Foundation (P0 CRITICAL) - ✅ Complete
**Status**: Complete (22/22 stories done, retrospective complete)
**Stories**: 22 stories
**Goal**: Provision complete cloud infrastructure, CI/CD pipelines, test infrastructure, and development environment.

**Key Deliverables:**
- Cloud infrastructure supporting both AWS and Azure (build-time choice):
  - **AWS**: EKS, RDS PostgreSQL, ElastiCache Redis, ECR, S3, IAM, VPC
  - **Azure**: AKS, PostgreSQL Flexible Server, Azure Cache for Redis, ACR, Key Vault, VNet
- GitHub Actions CI/CD pipelines with `CLOUD_PROVIDER` variable (PR checks, staging auto-deploy, production with approval)
- Test infrastructure (test databases, data factories, parallel runners, reporting)
- Monitoring stack (CloudWatch/Log Analytics, CloudTrail/Activity Log)
- Local development environment (Podman Compose)
- Third-party service provisioning (API keys, OAuth credentials)

**Success Criteria**: Deploy "Hello World" service to staging via CI/CD on either AWS or Azure, execute sample test suite, provision tenant schemas, view live metrics.

### Epic 1: Foundation & Administration (P1 HIGH) - 🚧 In Progress
**Status**: Active (Sprint 1 - Story 1-1 ready-for-dev, Story 1-2 drafted)
**Stories**: 13 stories (1 ready-for-dev, 1 drafted, 11 backlog)
**Goal**: User account management, organization setup, project creation, basic RBAC.

**Key Features:**
- User authentication (email/password, Google SSO, SAML)
- Organization creation and team invites
- Project creation and configuration
- Role-based access control (6 roles)
- Basic profile and notification settings

### Epic 2: AI Agent Platform & Executive Visibility (P1 HIGH)
**Status**: Backlog  
**Stories**: 18 stories  
**Goal**: Multi-agent AI system, document ingestion, test artifact generation, PM/CSM dashboards.

**Key Features:**
- Document ingestion (PDF, Word, Markdown)
- GitHub repository connection and code analysis
- DOM crawling with Playwright
- 3 MVP AI agents (BAConsultant AI Agent, QAConsultant AI Agent, AutomationConsultant AI Agent)
- Agent orchestration and pipeline management
- PM/CSM dashboards with KPIs and SLA monitoring

### Epic 3: Manual Testing & Developer Integration (P1 HIGH)
**Status**: Backlog  
**Stories**: 15 stories  
**Goal**: Manual test execution workflows, evidence capture, GitHub PR integration.

**Key Features:**
- Manual test checklist execution UI
- Evidence capture (screenshots, videos, notes)
- Defect filing and traceability
- GitHub PR integration (test results as comments, merge gates)
- Developer-friendly test result views

### Epic 4: Automated Execution & Self-Healing (P0 CRITICAL)
**Status**: Backlog  
**Stories**: 16 stories  
**Goal**: Automated test execution, self-healing automation, QA dashboards.

**Key Features:**
- Playwright test script execution (parallel, cross-browser)
- Containerized test runners with autoscaling
- Self-healing automation (DOM change detection, selector fallback)
- Approval workflows for auto-fixes
- QA dashboards (test runs, flaky tests, environment status)

### Epic 5: Complete Dashboards & Ecosystem Integration (P1 HIGH)
**Status**: Backlog  
**Stories**: 16 stories  
**Goal**: Complete integrations, advanced dashboards, reporting.

**Key Features:**
- JIRA bi-directional sync (import issues, auto-create defects)
- TestRail/Testworthy integration (import/export test plans)
- Slack ChatOps (notifications, commands)
- Advanced reporting (PDF exports, scheduled summaries)
- Integration health monitoring

### Epic 6: Advanced Features (Post-MVP)
**Status**: Backlog (P2)
**Stories**: 8 stories
**Goal**: Advanced AI agents, ML-based self-healing, enterprise features.

**Key Features:**
- Remaining 4 Post-MVP AI agents (AI Log Reader/Summarizer, Security Scanner Orchestrator, Performance/Load Agent, DatabaseConsultant AI Agent)
- ML-suggested robust selectors
- Advanced SLA monitoring
- Cost tracking per test/story point
- SOC2/ISO compliance preparation

**Estimated MVP Timeline**: 15-19 weeks (Epics 1-5) | Sprint 0 (Epic 0): ✅ Complete

---

## 🚀 Quick Start

### Prerequisites

#### Required Software
- **Python 3.11+** - Backend development (FastAPI)
- **Node.js 18+** (or 20.x LTS recommended) - Frontend development (Next.js)
- **PostgreSQL 15+** (with pgvector extension) - Database
- **Redis 7+** - Caching and job queue
- **Podman Desktop 1.x+** or **Docker Desktop** - Container runtime for local development
  - **Note**: Podman is preferred for 10Pearls systems per company policy
- **Git 2.40+** - Version control

#### Optional Software (Role-Specific)
- **Terraform 1.6+** - For infrastructure provisioning (DevOps/Infrastructure engineers)
- **kubectl 1.28+** - Kubernetes CLI (for production debugging, SRE/Platform engineers)
- **AWS CLI** - For AWS cloud resource management (DevOps engineers)
- **Azure CLI** - For Azure cloud resource management (DevOps engineers)

#### IDE/Editor (Choose One)
- **Cursor** (Recommended) - AI-powered IDE with built-in AI assistance
- **VS Code** - Standard development IDE
- **Claude Code** (Optional) - AI-powered IDE at claude.ai/code
- **IntelliJ IDEA / PyCharm** - Alternative IDE options

**Note about BMad Method**: BMad is **already included** in this repository (`.bmad/` directory). You do **NOT** need to install it separately. It's a development methodology framework that comes with the project.

**Note about Claude Code**: Claude Code is **optional**. The project works with any IDE. Claude Code provides enhanced AI assistance through BMad workflows, but it's not required for development.

### Development Setup

Epic 0 (Infrastructure Foundation) is complete. The local development environment is fully operational.

```bash
# Clone the repository
git clone <repository-url>
cd QUALISYS

# Set up environment variables
cp .env.example .env
# Edit .env with your local configuration

# Start local services (PostgreSQL, Redis, MailCatcher, API, Web)
podman-compose up -d

# Seed development data (3 tenants, 10 users, sample projects)
podman-compose exec api npx ts-node scripts/dev-seed.ts

# Access the application
# Web:  http://localhost:3000
# API:  http://localhost:3001
# Mail: http://localhost:1080
# Test credentials: admin@tenant-dev-1.test / password123
```

For the full local development guide, see [docs/local-development.md](./docs/local-development.md).

### Configuration

Copy the environment template and customize:
```bash
cp .env.example .env
```

Key variables (see `.env.example` for full list):
```bash
# Database
DATABASE_URL=postgresql://qualisys:qualisys@localhost:5432/qualisys_master

# Cache
REDIS_URL=redis://localhost:6379

# LLM Provider (MVP uses OpenAI)
OPENAI_API_KEY=your-openai-key

# Cloud Provider (aws or azure)
CLOUD_PROVIDER=aws
```

### Project Structure

```
QUALISYS/
├── docs/                    # Project documentation
│   ├── index.md            # Documentation index
│   ├── planning/          # PRD, product brief, UX design
│   ├── architecture/       # System architecture
│   ├── epics/             # Epic definitions
│   ├── tech-specs/        # Technical specifications
│   ├── stories/           # Story files
│   ├── reports/           # Validation reports
│   └── research/          # Market research
├── infrastructure/         # Infrastructure as Code
│   ├── terraform/         # Terraform (aws/ and azure/ roots)
│   └── kubernetes/        # K8s manifests (shared/, aws/, azure/)
├── api/                   # Python FastAPI backend
├── web/                   # Next.js frontend
├── e2e/                   # End-to-end test suites
├── playwright-runner/     # Playwright test runner service
├── .bmad/                 # BMad Method framework (included, no install needed)
│   ├── bmm/              # BMad Method Module (agents, workflows)
│   ├── bmb/             # BMad Builder Module
│   └── core/            # BMad Core framework
└── .claude/              # Claude Code commands (optional, auto-generated)
```

**For detailed setup instructions, see**: [Local Development Guide](./docs/local-development.md) | [Infrastructure README](./infrastructure/README.md)

---

## 👥 Team Member Onboarding

### First-Time Setup Checklist

When a team member pulls the project for the first time, they should:

1. ✅ **Install Required Software** (see Prerequisites above)
   - Python 3.11+, Node.js 18+, PostgreSQL 15+, Redis 7+, Podman/Docker, Git

2. ✅ **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd QUALISYS
   ```

3. ✅ **Set Up Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

4. ✅ **Install Dependencies**
   ```bash
   # Backend
   cd api
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt

   # Frontend
   cd ../web
   npm install
   ```

5. ✅ **Start Local Services**
   ```bash
   podman-compose up -d  # or docker-compose up -d
   ```

6. ✅ **Run Database Migrations**
   ```bash
   alembic upgrade head
   ```

7. ✅ **Choose Your IDE**
   - **Cursor** (recommended) - Best AI assistance, works out of the box
   - **VS Code** - Standard IDE, install recommended extensions
   - **Claude Code** - Optional, for enhanced BMad workflow support

### What You DON'T Need to Install

- ❌ **BMad Method** - Already included in `.bmad/` directory
- ❌ **Claude Code** - Optional, project works with any IDE
- ❌ **Kubernetes** - Only needed for production deployment (not local dev)
- ❌ **AWS/Azure Account** - Only needed for infrastructure work (Epic 0)

### IDE-Specific Setup

#### Cursor (Recommended)
- No additional setup needed
- BMad workflows work automatically via `.cursor/rules/bmad/`
- AI assistance available immediately

#### VS Code
- Install recommended extensions (will be listed in `.vscode/extensions.json`)
- BMad workflows accessible but may require manual activation

#### Claude Code (Optional)
- Visit claude.ai/code
- BMad workflows available via `.claude/commands/`
- Enhanced AI assistance for BMad workflows

### Getting Help

- **Documentation**: Start with [docs/index.md](./docs/index.md)
- **Architecture Questions**: See [docs/architecture/architecture.md](./docs/architecture/architecture.md)
- **Setup Issues**: See [Local Development Guide](./docs/local-development.md) or [Epic 0 Tech Spec](./docs/tech-specs/tech-spec-epic-0.md)
- **BMad Method**: See [CLAUDE.md](./CLAUDE.md) for workflow guidance

---

## 📖 Documentation

### Core Documents
- **[Documentation Index](./docs/index.md)** - Complete documentation overview and navigation
- **[Product Requirements Document](./docs/planning/prd.md)** - 110 functional requirements across 14 categories
- **[System Architecture](./docs/architecture/architecture.md)** - Technical design, risk analysis, architectural decisions
- **[Product Brief](./docs/planning/product-brief-QUALISYS-2025-12-01.md)** - Market positioning and strategic vision
- **[UX Design Specification](./docs/planning/ux-design-specification.md)** - 6 personas, 6 critical user flows

### Planning & Research
- **[Market Research](./docs/research/research-market-2025-11-30.md)** - Market size, trends, opportunities
- **[Competitive Research](./docs/research/research-competitive-2025-12-01.md)** - Competitive landscape analysis
- **[Test Design System](./docs/planning/test-design-system.md)** - Testing methodology and standards

### Implementation
- **[Epic Overview](./docs/epics/epics.md)** - All epics breakdown with story counts
- **[Epic 0: Infrastructure](./docs/epics/epic-0-infrastructure.md)** - Infrastructure foundation details
- **[Epic 0 Tech Spec](./docs/tech-specs/tech-spec-epic-0.md)** - Infrastructure technical specification
- **[Epic 1 Tech Spec](./docs/tech-specs/tech-spec-epic-1.md)** - Foundation & Administration tech spec

### Validation Reports
- **[PRD Validation Report](./docs/reports/validation-report-prd-20251211.md)** - PRD quality assessment
- **[Architecture Validation Report](./docs/reports/validation-report-architecture-20251211.md)** - Architecture review
- **[Implementation Readiness Report](./docs/reports/implementation-readiness-report-2026-01-22.md)** - Phase 3→4 transition validation

### API Documentation
- API Reference documentation (coming soon - Epic 1+)

---

## 🔒 Security & Compliance

### Authentication & Authorization
- **Multi-factor Auth**: TOTP-based two-factor authentication (optional)
- **SSO**: OAuth 2.0 (Google), SAML 2.0 (enterprise identity providers)
- **RBAC**: 6 role-based access control levels with granular permissions
- **Session Management**: JWT tokens with 7-day expiry, secure httpOnly cookies

### Data Protection
- **Encryption in Transit**: TLS 1.3 minimum for all API and web traffic
- **Encryption at Rest**: AES-256 encryption for sensitive data (API keys, credentials, test artifacts)
- **Database Encryption**: Encrypted PostgreSQL storage
- **PII Handling**: Automatic detection and redaction of sensitive data in logs and screenshots

### Compliance & Governance
- **GDPR Ready**: Data export (JSON/CSV), right to be forgotten, consent management
- **Data Retention**: Configurable policies (30/90/180/365 days) per tenant
- **Audit Logging**: Immutable audit logs of all administrative actions and data access
- **SOC 2 Type II**: Target certification Month 9 (Growth phase)
- **ISO 27001**: Optional, enterprise demand-driven

### Code Safety
- **Static Analysis**: Semgrep on all code commits
- **Dependency Scanning**: Weekly automated scans (Snyk, Dependabot)
- **Dynamic Testing**: OWASP ZAP scans on staging environments
- **Code Safety**: Semgrep, Snyk, Bandit for all generated code

---

## 🏗️ Development Methodology

QUALISYS is developed using the **BMad Method v6** - an AI-driven agile development framework that uses specialized AI agents and workflows to guide software development from conception to implementation.

### BMad Method Overview
- **Track**: Enterprise BMad Method (full 4-phase approach)
- **Current Phase**: Phase 4 - Implementation
- **Agents**: 12 specialized AI agents (PM, Architect, SM, DEV, TEA, Analyst, UX-Designer, Tech-Writer, etc.)
- **Workflows**: 34+ workflows across planning, solutioning, and implementation phases

### Key Workflows
- **Sprint Planning**: `/bmad:bmm:workflows:sprint-planning` - Initialize sprint tracking
- **Story Creation**: `/bmad:bmm:workflows:create-story` - Create and draft stories
- **Story Implementation**: `/bmad:bmm:workflows:dev-story` - Implement stories with DEV agent
- **Status Check**: `/bmad:bmm:workflows:workflow-status` - Check current project status

For more information about BMad Method, see the [BMad documentation](.bmad/bmm/docs/README.md) or [CLAUDE.md](./CLAUDE.md).

---

## 📈 Success Metrics

### Product Success Metrics
- **Time to First Test Suite**: <10 minutes from project creation to first generated test artifacts
- **Test Maintenance Reduction**: 70% reduction in time spent fixing broken tests
- **Test Coverage Improvement**: 40% increase in requirements coverage after 60 days
- **Self-Healing Success Rate**: 80% of test failures auto-fixed without human intervention
- **Monthly Retention**: >85% month-over-month retention for paid teams

### Business Metrics
- **Market Penetration**: 100 paying teams in first 12 months
- **Integration Adoption**: 70% of teams connect at least one integration
- **Target Users**: 60% software houses, 20% mid-size product companies, 20% freelance/consulting

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](./CONTRIBUTING.md) (coming soon).

**Development Process:**
1. Check current epic and story status in `docs/sprint-status.yaml`
2. Review relevant technical specifications in `docs/tech-specs/`
3. Follow BMad Method workflows for story implementation
4. Ensure all tests pass and code meets quality standards

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/10pearls/qualisys/issues)
- **Email**: support@qualisys.io
- **Documentation**: [Complete Documentation](./docs/index.md)

---

## 📄 License

[License details to be added]

---

## 🙏 Acknowledgments

Built with:
- [Playwright](https://playwright.dev/) - Browser automation
- [LangChain](https://langchain.com/) - LLM orchestration
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search in PostgreSQL
- [vLLM](https://github.com/vllm-project/vllm) - LLM inference engine
- [BMad Method](https://github.com/bmad-code) - AI-driven agile development framework

---

**Status**: Phase 4: Implementation (Epic 1 - Foundation & Administration)
**Version**: 0.1.0 (Pre-release)
**Last Updated**: 2026-02-12
