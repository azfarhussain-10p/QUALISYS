/**
 * Test Execution Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 6 - Test execution factory creates execution records
 */

import { faker } from '@faker-js/faker';
import { TestExecution, ExecutionStatus } from '../types/entities';

export interface TestExecutionFactoryOptions {
  id?: string;
  testCaseId?: string;
  status?: ExecutionStatus;
  executedBy?: string;
  environment?: string;
  browser?: string;
}

export class TestExecutionFactory {
  static create(options: TestExecutionFactoryOptions = {}): TestExecution {
    const status: ExecutionStatus =
      options.status ??
      faker.helpers.arrayElement(['passed', 'failed', 'skipped', 'blocked']);
    const startTime = faker.date.recent();
    const duration = faker.number.int({ min: 10, max: 300 });

    return {
      id: options.id ?? faker.string.uuid(),
      testCaseId: options.testCaseId ?? faker.string.uuid(),
      status,
      executedBy: options.executedBy ?? faker.string.uuid(),
      startTime,
      endTime: new Date(startTime.getTime() + duration * 1000),
      duration,
      environment:
        options.environment ??
        faker.helpers.arrayElement(['staging', 'production', 'local']),
      browser:
        options.browser ??
        faker.helpers.arrayElement(['chrome', 'firefox', 'safari', 'edge']),
      notes: status === 'failed' ? faker.lorem.sentence() : undefined,
      errorMessage:
        status === 'failed' ? faker.lorem.paragraph() : undefined,
      screenshots:
        status === 'failed'
          ? [`screenshots/${faker.string.uuid()}.png`]
          : [],
      createdAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: TestExecutionFactoryOptions = {}
  ): TestExecution[] {
    return Array.from({ length: count }, () => this.create(options));
  }
}
