// Health Check Endpoints
// Story: 0-11 Staging Auto-Deployment
// AC: 4 - Readiness + liveness probes
// AC: 5 - Rollback on failed health checks (Kubernetes uses probe responses)
//
// /health  - Liveness probe: is the process alive?
// /ready   - Readiness probe: is the service ready to accept traffic?
//
// Usage: import { registerHealthRoutes } from './health';
//        registerHealthRoutes(app);

import type { Express, Request, Response } from 'express';

interface HealthResponse {
  status: string;
  timestamp: string;
}

interface ReadyResponse extends HealthResponse {
  checks?: Record<string, string>;
  error?: string;
}

/**
 * Register /health and /ready endpoints on the Express app.
 *
 * @param app - Express application instance
 * @param deps - Optional dependency check functions (database, redis, etc.)
 */
export function registerHealthRoutes(
  app: Express,
  deps?: {
    checkDatabase?: () => Promise<void>;
    checkRedis?: () => Promise<void>;
  },
): void {
  // Liveness probe: returns 200 if the process is running
  app.get('/health', (_req: Request, res: Response) => {
    const body: HealthResponse = {
      status: 'ok',
      timestamp: new Date().toISOString(),
    };
    res.status(200).json(body);
  });

  // Readiness probe: returns 200 only if all dependencies are reachable
  app.get('/ready', async (_req: Request, res: Response) => {
    const checks: Record<string, string> = {};

    try {
      if (deps?.checkDatabase) {
        await deps.checkDatabase();
        checks.database = 'ok';
      }

      if (deps?.checkRedis) {
        await deps.checkRedis();
        checks.redis = 'ok';
      }

      const body: ReadyResponse = {
        status: 'ready',
        timestamp: new Date().toISOString(),
        checks,
      };
      res.status(200).json(body);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const body: ReadyResponse = {
        status: 'not ready',
        timestamp: new Date().toISOString(),
        checks,
        error: message,
      };
      res.status(503).json(body);
    }
  });
}
