# QUALISYS

**AI-Powered Testing Platform**

> Revolutionizing software testing through intelligent document ingestion, multi-agent AI capabilities, and self-healing test automation.

---

## 🎯 Project Vision

QUALISYS combines AI-powered document understanding, DOM analysis, and source code intelligence to automate the entire testing lifecycle - from test case generation to self-healing execution and comprehensive reporting.

## 📚 Documentation

**[→ View Complete Documentation](./docs/index.md)**

**Quick Links:**
- [Full Technical Specification](./docs/QUALISYS-Project-Documentation.md)
- [Architecture & Tech Stack](./docs/QUALISYS-Project-Documentation.md#2-architecture--data-flow-high-level)
- [Roadmap](./docs/QUALISYS-Project-Documentation.md#11-phased-roadmap-mvp--enterprise)

---

## ✨ Key Features

### 🤖 Multi-Agent AI System
- **8 specialized AI agents** for documentation analysis, test generation, automation, security scanning, and performance testing
- Intelligent orchestration and pipeline management
- User-selectable or automated agent workflows

### 📄 Intelligent Ingestion
- Parse PRDs, SRS, RFPs, and technical specs
- Clone and analyze GitHub repositories
- DOM crawling and scraping via Playwright
- Support for PDF, Word, Markdown, Confluence, emails

### 🔄 Self-Healing Test Automation
- Multiple selector strategies (CSS, XPath, text anchors, visual hashes)
- DOM change detection and auto-patching
- ML-suggested robust selectors
- Versioned artifacts with audit trails

### 📊 Comprehensive Dashboards
- PM/CSM dashboards: project health, coverage, velocity, SLA compliance
- QA dashboards: test runs, flaky tests, environment status
- Real-time KPIs and SLA monitoring
- Exportable PDF reports

### 🔗 Enterprise Integrations
- **Issue Tracking**: Jira, GitHub Issues
- **Test Management**: TestRail, Testworthy
- **CI/CD**: GitHub Actions, GitLab CI
- **ChatOps**: Slack, MS Teams
- **Auth**: SSO (SAML/OAuth/OIDC), Keycloak

---

## 🏗️ Tech Stack

### Frontend
- React + TypeScript + Next.js
- Tailwind + shadcn/ui
- Recharts for dashboards
- WebSocket/SSE for real-time updates

### Backend
- **Python FastAPI** + LangChain (agent orchestration)
- **Node.js (NestJS)** (optional integrations)
- Celery / RQ / RabbitMQ (job distribution)

### AI & ML
- **LLM**: Llama 3.1 (reasoning) + Codestral (code generation)
- **Hosting**: Ollama (dev) → vLLM (production)
- **Embeddings**: sentence-transformers
- **Observability**: LangFuse

### Databases
- **Relational**: PostgreSQL (prod), SQLite (proto)
- **Vector**: Qdrant / Weaviate (self-hosted)
- **Cache**: Redis
- **Object Storage**: MinIO / S3
- **Timeseries**: Prometheus / Timescale

### Testing & Security
- **E2E**: Playwright + Puppeteer
- **Load/Perf**: k6, Locust
- **Security**: OWASP ZAP, Snyk
- **API**: Postman/Newman, REST-assured

### Infrastructure
- **Orchestration**: Kubernetes + Helm
- **CI/CD**: GitHub Actions
- **Secrets**: HashiCorp Vault
- **GPU**: NVIDIA A100/H100 for LLM serving

---

## 🎯 Target Audience

- **PM / CSM** - Project oversight, SLA management, reporting
- **Manual Test Engineers** - Guided test execution, evidence capture
- **Automation Engineers** - Generated scripts, self-healing automation
- **SRE/Platform** - Infrastructure monitoring, performance testing

---

## 🗺️ Roadmap

### MVP (6–10 weeks)
- ✅ Auth & project creation
- ✅ Document ingestion + vector store
- ✅ Playwright DOM crawler
- ✅ Basic test case generator
- ✅ Simple runner + Jira integration
- ✅ Basic dashboards

### v1 (3–6 months)
- 🔄 Multi-agent orchestration
- 🔄 Self-healing POC
- 🔄 BDD generator
- 🔄 Parallel cross-browser runners
- 🔄 LLM observability (LangFuse)

### Enterprise (6–12 months)
- 📅 vLLM production serving
- 📅 SOC2/ISO compliance
- 📅 Multi-region deployment
- 📅 Advanced security testing
- 📅 Full cost tracking

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Docker & Kubernetes (for production)

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd QUALISYS

# Install dependencies
pip install -r requirements.txt
npm install

# Set up databases
docker-compose up -d postgres redis qdrant

# Run migrations
alembic upgrade head

# Start development servers
npm run dev          # Frontend
uvicorn main:app     # Backend
```

### Configuration

Create `.env` file:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/qualisys
REDIS_URL=redis://localhost:6379
VECTOR_DB_URL=http://localhost:6333
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 📖 Documentation

- **[Complete Documentation](./docs/index.md)** - Start here
- **[Technical Specification](./docs/QUALISYS-Project-Documentation.md)** - Full details
- **[Architecture](./docs/QUALISYS-Project-Documentation.md#2-architecture--data-flow-high-level)** - System design
- **[Security & Compliance](./docs/QUALISYS-Project-Documentation.md#8-security-compliance--governance)** - Standards
- **[API Reference](./docs/api/)** - API documentation (coming soon)

---

## 🔒 Security & Compliance

- **Auth**: OAuth2/OIDC, SAML SSO, RBAC
- **Encryption**: TLS in transit, AES-256 at rest
- **Compliance**: ISO27001, SOC2, GDPR ready
- **Audit**: Immutable audit logs
- **Code Safety**: Semgrep, Snyk, Bandit for all generated code

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](./CONTRIBUTING.md) (coming soon).

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/10pearls/qualisys/issues)
- **Email**: support@qualisys.io
- **Slack**: [Join our community](#)

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
- [Qdrant](https://qdrant.tech/) - Vector database
- [vLLM](https://github.com/vllm-project/vllm) - LLM inference engine

---

**Status**: 🚧 Planning & Design Phase
**Version**: 0.1.0 (Pre-release)
**Last Updated**: 2025-11-30
