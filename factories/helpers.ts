/**
 * Factory Association Helpers
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 8 - Factories support associations (user belongs to organization)
 *
 * Provides helper functions for creating related entity graphs
 * with proper foreign key references and tenant isolation.
 */

import { UserFactory } from './UserFactory';
import { OrganizationFactory } from './OrganizationFactory';
import { ProjectFactory } from './ProjectFactory';
import { TeamFactory } from './TeamFactory';
import { TestCaseFactory } from './TestCaseFactory';
import { TestExecutionFactory } from './TestExecutionFactory';
import {
  User,
  Organization,
  Project,
  Team,
  TestCase,
  TestExecution,
} from '../types/entities';

// =============================================================================
// Composite Entity Graphs
// =============================================================================

export interface TenantGraph {
  organization: Organization;
  users: User[];
  projects: Project[];
  teams: Team[];
}

export interface ProjectGraph {
  project: Project;
  testCases: TestCase[];
  executions: TestExecution[];
}

/**
 * Creates a full tenant entity graph:
 * 1 organization + N users + N projects + 1 team
 */
export function createTenantGraph(options: {
  tenantId?: string;
  orgName?: string;
  userCount?: number;
  projectCount?: number;
} = {}): TenantGraph {
  const organization = OrganizationFactory.create({
    tenantId: options.tenantId,
    name: options.orgName,
  });

  const userCount = options.userCount ?? 3;
  const users = UserFactory.createMany(userCount, {
    organizationId: organization.id,
  });
  // First user is always admin
  if (users.length > 0) {
    users[0] = { ...users[0], role: 'admin' };
  }

  const projectCount = options.projectCount ?? 2;
  const projects = ProjectFactory.createMany(projectCount, {
    organizationId: organization.id,
  });

  const teams = [
    TeamFactory.create({
      organizationId: organization.id,
      name: 'Default Team',
      memberIds: users.map((u) => u.id),
    }),
  ];

  return { organization, users, projects, teams };
}

/**
 * Creates a project with test cases and executions:
 * 1 project + N test cases + 1 execution per test case
 */
export function createProjectGraph(options: {
  organizationId?: string;
  testCaseCount?: number;
} = {}): ProjectGraph {
  const project = ProjectFactory.create({
    organizationId: options.organizationId,
  });

  const testCaseCount = options.testCaseCount ?? 5;
  const testCases = TestCaseFactory.createMany(testCaseCount, {
    projectId: project.id,
  });

  const executions = testCases.map((tc) =>
    TestExecutionFactory.create({ testCaseId: tc.id })
  );

  return { project, testCases, executions };
}
