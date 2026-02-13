// Structured JSON Logger for QUALISYS
// Story: 0-20 Log Aggregation
// AC: 5  - Logs structured in JSON format
// AC: 6  - Logs include timestamp, level, message, trace_id, tenant_id
// AC: 12 - Cross-service trace correlation via trace_id

import pino from 'pino';
import { v4 as uuidv4 } from 'uuid';
import type { Request, Response, NextFunction } from 'express';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LogContext {
  trace_id?: string;
  tenant_id?: string;
  user_id?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Base Pino instance (AC5: JSON, AC6: required fields)
// ---------------------------------------------------------------------------

const baseLogger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
  timestamp: () => `,"timestamp":"${new Date().toISOString()}"`,
  base: {
    service: 'qualisys-api',
    environment: process.env.NODE_ENV || 'development',
  },
});

// ---------------------------------------------------------------------------
// Logger class — holds per-request context (trace_id, tenant_id)
// ---------------------------------------------------------------------------

class Logger {
  private context: LogContext = {};

  setContext(ctx: LogContext): void {
    this.context = { ...this.context, ...ctx };
  }

  setTraceId(traceId: string): void {
    this.context.trace_id = traceId;
  }

  setTenantId(tenantId: string): void {
    this.context.tenant_id = tenantId;
  }

  child(): Logger {
    const childLogger = new Logger();
    childLogger.context = { ...this.context };
    return childLogger;
  }

  debug(message: string, data?: object): void {
    baseLogger.debug({ ...this.context, ...data }, message);
  }

  info(message: string, data?: object): void {
    baseLogger.info({ ...this.context, ...data }, message);
  }

  warn(message: string, data?: object): void {
    baseLogger.warn({ ...this.context, ...data }, message);
  }

  error(message: string, error?: Error, data?: object): void {
    baseLogger.error(
      {
        ...this.context,
        ...data,
        ...(error
          ? {
              error: {
                name: error.name,
                message: error.message,
                stack: error.stack,
              },
            }
          : {}),
      },
      message,
    );
  }
}

// Singleton for non-request contexts (startup, background jobs)
export const logger = new Logger();

// ---------------------------------------------------------------------------
// Express middleware — attaches trace_id + tenant_id, logs requests (AC6, AC12)
// ---------------------------------------------------------------------------

export function loggingMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  // AC12: trace_id from X-Request-ID header or generate new UUID
  const traceId =
    (req.headers['x-request-id'] as string | undefined) || uuidv4();
  // AC6: tenant_id from header (set by auth middleware in production)
  const tenantId =
    (req.headers['x-tenant-id'] as string | undefined) || 'unknown';

  // Propagate trace_id in response for downstream correlation
  res.setHeader('X-Request-ID', traceId);

  // Create per-request logger
  const reqLogger = new Logger();
  reqLogger.setTraceId(traceId);
  reqLogger.setTenantId(tenantId);

  // Attach to request for handler use
  (req as Request & { log: Logger }).log = reqLogger;

  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    const statusCode = res.statusCode;
    const level = statusCode >= 500 ? 'error' : statusCode >= 400 ? 'warn' : 'info';
    const logData = {
      method: req.method,
      path: req.path,
      status: statusCode,
      duration_ms: duration,
      user_agent: req.headers['user-agent'],
    };

    if (level === 'error') {
      reqLogger.error('HTTP Request', undefined, logData);
    } else if (level === 'warn') {
      reqLogger.warn('HTTP Request', logData);
    } else {
      reqLogger.info('HTTP Request', logData);
    }
  });

  next();
}

export { Logger };
