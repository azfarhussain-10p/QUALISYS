/**
 * Test Utilities — Public API
 * Story: 0-18 Multi-Tenant Test Isolation Infrastructure
 * AC: 10 - Test utilities documented with usage examples
 *
 * Usage:
 *   import {
 *     createTestTenant,
 *     cleanupTestTenant,
 *     setTenantContext,
 *     clearTenantContext,
 *     requireTenantContext,
 *     seedTestTenant,
 *     useTenantIsolation,
 *     withTenantIsolation,
 *   } from '../src/test-utils';
 */

// Core tenant lifecycle
export {
  createTestTenant,
  cleanupTestTenant,
  setTenantContext,
  clearTenantContext,
  requireTenantContext,
  seedTestTenant,
} from './tenant-isolation';

export type { TestTenant } from './tenant-isolation';

// Jest integration
export {
  useTenantIsolation,
  withTenantIsolation,
} from './tenant-fixtures';

export type { TenantTestContext } from './tenant-fixtures';
