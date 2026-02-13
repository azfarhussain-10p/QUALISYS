/**
 * Test Case Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 5 - Test case factory creates test cases with steps
 */

import { faker } from '@faker-js/faker';
import {
  TestCase,
  TestStep,
  TestCasePriority,
  TestCaseStatus,
} from '../types/entities';

export interface TestCaseFactoryOptions {
  id?: string;
  projectId?: string;
  title?: string;
  stepsCount?: number;
  priority?: TestCasePriority;
  status?: TestCaseStatus;
  tags?: string[];
}

export class TestCaseFactory {
  static create(options: TestCaseFactoryOptions = {}): TestCase {
    const stepsCount =
      options.stepsCount ?? faker.number.int({ min: 3, max: 10 });

    return {
      id: options.id ?? faker.string.uuid(),
      projectId: options.projectId ?? faker.string.uuid(),
      title: options.title ?? faker.lorem.sentence(),
      description: faker.lorem.paragraph(),
      priority:
        options.priority ??
        faker.helpers.arrayElement([
          'low',
          'medium',
          'high',
          'critical',
        ]),
      status: options.status ?? 'active',
      steps: this.createSteps(stepsCount),
      tags:
        options.tags ??
        faker.helpers.arrayElements(
          ['smoke', 'regression', 'e2e', 'api', 'ui', 'security'],
          { min: 1, max: 3 }
        ),
      estimatedDuration: faker.number.int({ min: 60, max: 600 }),
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: TestCaseFactoryOptions = {}
  ): TestCase[] {
    return Array.from({ length: count }, () => this.create(options));
  }

  private static createSteps(count: number): TestStep[] {
    return Array.from({ length: count }, (_, index) => ({
      id: faker.string.uuid(),
      order: index + 1,
      action: faker.lorem.sentence(),
      expectedResult: faker.lorem.sentence(),
      data: faker.datatype.boolean()
        ? { input: faker.lorem.word() }
        : undefined,
    }));
  }
}
