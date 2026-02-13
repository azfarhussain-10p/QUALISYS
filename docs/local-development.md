# QUALISYS Local Development Setup

Story: 0-21 Local Development Environment (Podman Compose)

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| **Podman Desktop** | 1.x+ | [podman-desktop.io](https://podman-desktop.io/) |
| **podman-compose** | 1.x+ | `pip install podman-compose` (or included with Podman Desktop) |
| Node.js | 20+ | Optional — only needed for running scripts outside containers |
| Git | 2.x+ | Required |

> **Important**: Docker Desktop is **NOT approved** for 10Pearls systems per company policy (January 2026). Use Podman Desktop or Podman CLI.

### Windows-Specific Setup

```bash
# Install Podman via winget
winget install RedHat.Podman

# Initialize and start Podman machine
podman machine init --cpus 4 --memory 4096
podman machine start
```

### macOS-Specific Setup

```bash
# Install Podman via Homebrew
brew install podman podman-compose

# Initialize and start Podman machine
podman machine init --cpus 4 --memory 4096
podman machine start
```

### Linux Setup

```bash
# Fedora/RHEL
sudo dnf install podman podman-compose

# Ubuntu/Debian
sudo apt install podman
pip install podman-compose
```

## Quick Start (< 30 minutes)

### 1. Clone Repository

```bash
git clone https://github.com/qualisys/qualisys.git
cd qualisys
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed — defaults work for local development
```

### 3. Start All Services

```bash
podman-compose up -d
```

Wait for all health checks to pass (~60 seconds):

```bash
podman-compose ps
# All services should show "healthy"
```

### 4. Seed Development Data

```bash
podman-compose exec api npx ts-node scripts/dev-seed.ts
```

### 5. Access the Application

| Service | URL | Purpose |
|---------|-----|---------|
| **Web App** | http://localhost:3000 | Next.js frontend |
| **API** | http://localhost:3001 | Express backend |
| **API Health** | http://localhost:3001/health | Health check endpoint |
| **MailCatcher** | http://localhost:1080 | Email testing UI |
| **PostgreSQL** | localhost:5432 | Database (user: `qualisys`) |
| **Redis** | localhost:6379 | Cache |

### Test Credentials

After running the seed script:

- **Email**: `admin@tenant-dev-1.test`
- **Password**: `password123`

## Common Commands

```bash
# Start all services (detached)
podman-compose up -d

# Start with rebuild (after Containerfile changes)
podman-compose up -d --build

# View all logs
podman-compose logs -f

# View specific service logs
podman-compose logs -f api
podman-compose logs -f web

# Stop all services
podman-compose down

# Stop and remove volumes (full reset)
podman-compose down -v

# Run a command in the API container
podman-compose exec api npm test

# Access PostgreSQL CLI
podman-compose exec postgres psql -U qualisys -d qualisys_master

# Access Redis CLI
podman-compose exec redis redis-cli

# Re-seed the database
podman-compose exec api npx ts-node scripts/dev-seed.ts
```

## Hot Reload

Both application services have hot reload enabled:

- **API** (`api/src/`): Uses `ts-node-dev --respawn --poll` — saves trigger automatic restart
- **Web** (`web/src/`): Uses Next.js Fast Refresh — changes appear instantly without full reload

Volume mounts in `compose.yml` map host source directories into containers:
- `./api/src` → `/app/src` (API)
- `./web/src` → `/app/src` (Web)
- `./web/public` → `/app/public` (Web static assets)

Named volumes (`api_node_modules`, `web_node_modules`) keep `node_modules` inside the container for performance.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  qualisys-network                     │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │  Web      │  │  API      │  │  MailCatcher       │ │
│  │  :3000    │──│  :3001    │──│  SMTP:1025 UI:1080 │ │
│  └──────────┘  └─────┬─────┘  └────────────────────┘ │
│                      │                                 │
│             ┌────────┴────────┐                       │
│             │                 │                       │
│       ┌─────┴─────┐   ┌──────┴─────┐                │
│       │ PostgreSQL │   │   Redis    │                │
│       │   :5432    │   │   :6379    │                │
│       └───────────┘   └────────────┘                │
│                                                       │
└─────────────────────────────────────────────────────┘
```

## Database

### Schemas

The local PostgreSQL instance mirrors the multi-tenant schema-per-tenant architecture:

| Schema | Purpose |
|--------|---------|
| `public` | Tenant registry (`organizations` table) |
| `tenant_dev_1` | Development tenant Alpha (enterprise plan) |
| `tenant_dev_2` | Development tenant Beta (free plan) |

### Connecting

```bash
# Via podman-compose
podman-compose exec postgres psql -U qualisys -d qualisys_master

# Direct connection (host)
psql postgresql://qualisys:qualisys_dev@localhost:5432/qualisys_master

# List schemas
\dn

# Query a tenant schema
SET app.current_tenant = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
SELECT * FROM tenant_dev_1.users;
```

### Reset Database

```bash
podman-compose down -v           # Remove volumes
podman-compose up -d postgres    # Recreate with init script
podman-compose up -d             # Start all services
podman-compose exec api npx ts-node scripts/dev-seed.ts  # Re-seed
```

## Email Testing

MailCatcher intercepts all SMTP email sent by the API:

1. Open http://localhost:1080
2. Trigger an email action in the app (password reset, invitation, etc.)
3. View the captured email in the MailCatcher web UI

SMTP configuration in compose.yml:
- Host: `mailcatcher` (container name, resolved via Podman network)
- Port: `1025`

## Troubleshooting

### Port Conflicts

If you see "address already in use" errors:

```bash
# Windows: find process using a port
netstat -ano | findstr :3000

# macOS/Linux: find process using a port
lsof -i :3000

# Kill the process or change ports in .env / compose.yml
```

Default ports: 3000 (Web), 3001 (API), 5432 (PostgreSQL), 6379 (Redis), 1080/1025 (MailCatcher).

### Podman Machine Issues (Windows/macOS)

```bash
# Check machine status
podman machine list

# Restart machine
podman machine stop && podman machine start

# Full reset (if persistent issues)
podman machine rm
podman machine init --cpus 4 --memory 4096
podman machine start
```

### Container Build Failures

```bash
# Clean build cache and retry
podman system prune -f
podman-compose up -d --build
```

### Database Connection Refused

```bash
# Check PostgreSQL is running and healthy
podman-compose ps postgres

# View PostgreSQL logs
podman-compose logs postgres

# Common cause: init script syntax error
podman-compose down -v
podman-compose up -d
```

### Hot Reload Not Working

**Windows (WSL2)**: Ensure the project is on the WSL filesystem (`/home/...`), not on the Windows mount (`/mnt/c/...`). File watching doesn't work across filesystem boundaries.

**Windows (native Podman)**: The `--poll` flag on ts-node-dev and `WATCHPACK_POLLING=true` for Next.js enable polling-based file watching, which works on all platforms but uses more CPU.

**General**: Ensure the Podman machine has sufficient resources:
- Podman Desktop → Settings → Resources → Podman Machine
- Allocate at least 4 GB RAM and 4 CPUs

### SELinux Issues (Fedora/RHEL)

Volume mounts use the `:Z` suffix for SELinux relabeling. If you still see permission denied:

```bash
sudo setsebool -P container_manage_cgroup true
```

### node_modules Issues

If dependencies seem stale after a `package.json` change:

```bash
# Remove named volumes and rebuild
podman-compose down -v
podman-compose up -d --build
```

## Performance Tips

- **Named volumes** for `node_modules` avoid slow host filesystem I/O
- **Podman is daemonless** — no background process consuming resources when idle
- Allocate **4+ GB RAM** to the Podman machine (Windows/macOS)
- On Linux, Podman runs rootless natively — no VM overhead

## File Reference

```
/
├── compose.yml                     # Podman Compose services
├── .env.example                    # Environment template (copy to .env)
├── .env                            # Local config (gitignored)
├── api/
│   ├── Containerfile.dev           # Dev container (hot reload)
│   ├── Dockerfile                  # Production build
│   └── src/                        # Source code (mounted into container)
├── web/
│   ├── Containerfile.dev           # Dev container (fast refresh)
│   ├── Dockerfile                  # Production build
│   └── src/                        # Source code (mounted into container)
├── scripts/
│   ├── init-local-db.sql           # PostgreSQL init (runs on first up)
│   ├── dev-seed.ts                 # Dev data seeding
│   ├── seed.ts                     # Test data seeding (Story 0-15)
│   └── init-test-db.sql            # Test DB init (Story 0-14)
└── docs/
    └── local-development.md        # This file
```
