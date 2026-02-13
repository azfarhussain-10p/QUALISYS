/**
 * QUALISYS Entity Type Definitions
 * Story: 0-15 Test Data Factories & Seeding
 *
 * Shared TypeScript types for domain entities used by factories,
 * seed scripts, and application code.
 */

// =============================================================================
// Enums and Literal Types
// =============================================================================

export type UserRole = 'admin' | 'member' | 'viewer';

export type OrgPlan = 'free' | 'pro' | 'enterprise';

export type TestCasePriority = 'low' | 'medium' | 'high' | 'critical';

export type TestCaseStatus = 'active' | 'draft' | 'deprecated' | 'archived';

export type ExecutionStatus = 'passed' | 'failed' | 'skipped' | 'blocked';

export type DefectSeverity = 'low' | 'medium' | 'high' | 'critical';

export type DefectStatus = 'open' | 'in_progress' | 'resolved' | 'closed' | 'wont_fix';

// =============================================================================
// Core Entities
// =============================================================================

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  organizationId: string;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  tenantId: string;
  schemaName: string;
  plan: OrgPlan;
  settings: OrgSettings;
  createdAt: Date;
  updatedAt: Date;
}

export interface OrgSettings {
  maxUsers: number;
  maxProjects: number;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  organizationId: string;
  settings: ProjectSettings;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface ProjectSettings {
  defaultBrowser: string;
  parallelExecutions: number;
  retryCount: number;
}

export interface Team {
  id: string;
  name: string;
  organizationId: string;
  memberIds: string[];
  createdAt: Date;
  updatedAt: Date;
}

// =============================================================================
// Testing Entities
// =============================================================================

export interface TestStep {
  id: string;
  order: number;
  action: string;
  expectedResult: string;
  data?: Record<string, unknown>;
}

export interface TestCase {
  id: string;
  projectId: string;
  title: string;
  description: string;
  priority: TestCasePriority;
  status: TestCaseStatus;
  steps: TestStep[];
  tags: string[];
  estimatedDuration: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface TestSuite {
  id: string;
  projectId: string;
  name: string;
  description: string;
  testCaseIds: string[];
  createdAt: Date;
  updatedAt: Date;
}

export interface TestExecution {
  id: string;
  testCaseId: string;
  status: ExecutionStatus;
  executedBy: string;
  startTime: Date;
  endTime: Date;
  duration: number;
  environment: string;
  browser: string;
  notes?: string;
  errorMessage?: string;
  screenshots: string[];
  createdAt: Date;
}

export interface TestEvidence {
  id: string;
  executionId: string;
  type: 'screenshot' | 'video' | 'log' | 'har';
  filePath: string;
  fileSize: number;
  caption?: string;
  createdAt: Date;
}

export interface Defect {
  id: string;
  executionId: string;
  projectId: string;
  title: string;
  description: string;
  severity: DefectSeverity;
  status: DefectStatus;
  assigneeId?: string;
  stepsToReproduce: string[];
  createdAt: Date;
  updatedAt: Date;
}
