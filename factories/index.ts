/**
 * Test Data Factories — Public API
 * Story: 0-15 Test Data Factories & Seeding
 *
 * Usage:
 *   import { UserFactory, ProjectFactory, createTenantGraph } from '../factories';
 *
 *   const user = UserFactory.create({ role: 'admin' });
 *   const users = UserFactory.createMany(5, { organizationId: org.id });
 *   const graph = createTenantGraph({ userCount: 3, projectCount: 2 });
 */

// Core entity factories
export { UserFactory } from './UserFactory';
export type { UserFactoryOptions } from './UserFactory';

export { OrganizationFactory } from './OrganizationFactory';
export type { OrganizationFactoryOptions } from './OrganizationFactory';

export { ProjectFactory } from './ProjectFactory';
export type { ProjectFactoryOptions } from './ProjectFactory';

export { TeamFactory } from './TeamFactory';
export type { TeamFactoryOptions } from './TeamFactory';

// Testing entity factories
export { TestCaseFactory } from './TestCaseFactory';
export type { TestCaseFactoryOptions } from './TestCaseFactory';

export { TestSuiteFactory } from './TestSuiteFactory';
export type { TestSuiteFactoryOptions } from './TestSuiteFactory';

export { TestExecutionFactory } from './TestExecutionFactory';
export type { TestExecutionFactoryOptions } from './TestExecutionFactory';

export { TestEvidenceFactory } from './TestEvidenceFactory';
export type { TestEvidenceFactoryOptions } from './TestEvidenceFactory';

export { DefectFactory } from './DefectFactory';
export type { DefectFactoryOptions } from './DefectFactory';

// Association helpers
export {
  createTenantGraph,
  createProjectGraph,
} from './helpers';
export type { TenantGraph, ProjectGraph } from './helpers';
