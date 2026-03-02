# QUALISYS Web Frontend

React 18 frontend for the QUALISYS AI System Quality Assurance Platform. Built with Vite, TypeScript, Tailwind CSS, and shadcn/ui.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.x | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | 6.x | Build tool and dev server |
| Tailwind CSS | 4.x | Utility-first styling |
| shadcn/ui | latest | Accessible component library |
| Axios | 1.x | HTTP client with refresh interceptor |
| Recharts | 2.x | Dashboard charts (LineChart, BarChart) |
| Monaco Editor | 4.x | In-browser code/text editor for artifact editing |
| React Router | 6.x | Client-side routing |

## Prerequisites

- Node.js 18+ (20.x LTS recommended)
- npm 9+

## Setup

```bash
# Install dependencies
npm install

# Configure environment
cp ../.env.example .env.local
# Edit .env.local — set VITE_API_URL if backend is not on localhost:8000
```

## Development

```bash
# Start the dev server (hot-reload)
npm run dev
```

App is available at `http://localhost:3000`.

> **Note:** The backend API must be running at `http://localhost:8000` (or the URL set in `VITE_API_URL`).

## Build & Preview

```bash
# Production build
npm run build

# Preview the production build locally
npm run preview
```

## Project Structure

```
web/
├── src/
│   ├── main.tsx                # Entry point
│   ├── App.tsx                 # Root router + route definitions
│   ├── index.css               # Tailwind base styles
│   ├── lib/
│   │   └── api.ts              # Axios client + all API functions (namespaced by domain)
│   ├── components/
│   │   ├── ui/                 # shadcn/ui primitives (Button, Dialog, Table, etc.)
│   │   ├── layout/             # AppHeader, Sidebar, PageLayout
│   │   ├── admin/              # MetricCard and other admin widgets
│   │   └── dashboard/          # PM dashboard components (TrendBadge, CoverageMatrix, etc.)
│   └── pages/
│       ├── auth/               # Login, Register, VerifyEmail, PasswordReset, SelectOrg
│       ├── admin/              # Dashboard, AuditLogs (Owner/Admin only)
│       ├── create-org/         # Organisation creation wizard
│       ├── dashboard/          # Org-level projects grid (ProjectsGridPage)
│       ├── invite/             # Invitation acceptance flow
│       ├── projects/           # Per-project sub-pages
│       │   ├── agents/         # AgentsTab — agent selection + SSE progress tracking
│       │   ├── artifacts/      # ArtifactsTab — artifact viewer + Monaco editor
│       │   ├── dashboard/      # DashboardPage — project health, coverage, SSE refresh
│       │   └── ...             # Documents, GitHub, Crawls tabs
│       └── settings/           # Profile, Security (MFA, sessions), Notifications
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## API Client

All API calls go through `src/lib/api.ts`. It exports namespaced objects:

```typescript
import { authApi, projectApi, artifactApi, dashboardApi } from '@/lib/api'

// Example
const projects = await projectApi.list(orgId)
const health   = await dashboardApi.getProjectHealth(orgId, projectId)
```

The Axios client automatically:
- Sends `httpOnly` cookies with every request (`withCredentials: true`)
- Retries once on `401 Unauthorized` by calling the refresh token endpoint
- Normalises error responses to `{ error: { code, message } }`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API base URL | `http://localhost:8000` |

## Key Conventions

- **Route params:** `orgId` maps to tenant slug, `projectId` is a UUID
- **SSE:** Use native `EventSource` (not Axios) for streaming endpoints — see `AgentsTab.tsx` and `DashboardPage` for the established pattern
- **Monaco Editor:** Import from `@monaco-editor/react`. `Editor` for editing, `DiffEditor` for two-version comparison
- **Error handling:** Always destructure `error.response.data.detail.error` for API error codes

## Running Tests

```bash
npm run test          # Run Vitest unit tests
npm run test:ui       # Vitest with browser UI
```

## Related Documentation

- [Backend README](../backend/README.md) — API setup and architecture
- [API Patterns](../backend/src/patterns/README.md) — SSE, LLM, pgvector contracts
- [UX Design Specification](../docs/planning/ux-design-specification.md) — 6 personas, 6 flows, design system
- [UI Mockups](../docs/designs/mockups/) — 8 workflow screen mockups
- [System Architecture](../docs/architecture/architecture.md) — Full technical design
