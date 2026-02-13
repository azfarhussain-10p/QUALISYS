/**
 * Test Suite Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 5 - Test case factory creates test cases with steps (suites group test cases)
 */

import { faker } from '@faker-js/faker';
import { TestSuite } from '../types/entities';

export interface TestSuiteFactoryOptions {
  id?: string;
  projectId?: string;
  name?: string;
  testCaseIds?: string[];
}

export class TestSuiteFactory {
  static create(options: TestSuiteFactoryOptions = {}): TestSuite {
    return {
      id: options.id ?? faker.string.uuid(),
      projectId: options.projectId ?? faker.string.uuid(),
      name:
        options.name ??
        `${faker.helpers.arrayElement(['Smoke', 'Regression', 'E2E', 'API', 'Security'])} Suite`,
      description: faker.lorem.sentence(),
      testCaseIds: options.testCaseIds ?? [],
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: TestSuiteFactoryOptions = {}
  ): TestSuite[] {
    return Array.from({ length: count }, () => this.create(options));
  }
}
