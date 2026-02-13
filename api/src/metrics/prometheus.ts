// Application Metrics — Prometheus Integration
// Story: 0-19 Monitoring Infrastructure (Prometheus + Grafana)
// AC: 3 - Prometheus scrapes application pod metrics via /metrics endpoint
//
// Exports prom-client registry, standard HTTP metrics, and Express middleware.
// Mount via: app.use(metricsMiddleware); app.get('/metrics', metricsHandler);

import {
  Registry,
  Counter,
  Histogram,
  Gauge,
  collectDefaultMetrics,
} from 'prom-client';
import type { Request, Response, NextFunction } from 'express';

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------
export const register = new Registry();

register.setDefaultLabels({ app: 'qualisys-api' });

// Collect default Node.js / process metrics (GC, heap, event loop, etc.)
collectDefaultMetrics({ register });

// ---------------------------------------------------------------------------
// HTTP Metrics (Task 2.4)
// ---------------------------------------------------------------------------

/** Total HTTP requests — labelled by method, route, status code. */
export const httpRequestsTotal = new Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status'] as const,
  registers: [register],
});

/** HTTP request duration in seconds — histogram with standard buckets. */
export const httpRequestDuration = new Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status'] as const,
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  registers: [register],
});

/** Currently in-flight HTTP requests. */
export const httpRequestsInFlight = new Gauge({
  name: 'http_requests_in_flight',
  help: 'Number of HTTP requests currently being processed',
  registers: [register],
});

// ---------------------------------------------------------------------------
// Middleware (Task 2.3)
// ---------------------------------------------------------------------------

/**
 * Express middleware that records request count, duration, and in-flight gauge.
 *
 * Place early in the middleware chain — before route handlers — so every
 * request is instrumented.
 */
export function metricsMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  // Skip instrumenting the /metrics endpoint itself
  if (req.path === '/metrics') {
    next();
    return;
  }

  const start = process.hrtime.bigint();
  httpRequestsInFlight.inc();

  res.on('finish', () => {
    const durationNs = Number(process.hrtime.bigint() - start);
    const durationSec = durationNs / 1e9;
    const route = req.route?.path ?? req.path;
    const labels = {
      method: req.method,
      route,
      status: String(res.statusCode),
    };

    httpRequestsTotal.inc(labels);
    httpRequestDuration.observe(labels, durationSec);
    httpRequestsInFlight.dec();
  });

  next();
}

// ---------------------------------------------------------------------------
// /metrics Handler (Task 2.3)
// ---------------------------------------------------------------------------

/**
 * Express route handler that returns Prometheus text exposition format.
 *
 * Mount: `app.get('/metrics', metricsHandler);`
 */
export async function metricsHandler(
  _req: Request,
  res: Response,
): Promise<void> {
  res.set('Content-Type', register.contentType);
  res.send(await register.metrics());
}
