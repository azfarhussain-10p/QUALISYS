/**
 * Defect Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 6 - Test execution factory creates execution records (defects linked to executions)
 */

import { faker } from '@faker-js/faker';
import { Defect, DefectSeverity, DefectStatus } from '../types/entities';

export interface DefectFactoryOptions {
  id?: string;
  executionId?: string;
  projectId?: string;
  severity?: DefectSeverity;
  status?: DefectStatus;
  assigneeId?: string;
}

export class DefectFactory {
  static create(options: DefectFactoryOptions = {}): Defect {
    return {
      id: options.id ?? faker.string.uuid(),
      executionId: options.executionId ?? faker.string.uuid(),
      projectId: options.projectId ?? faker.string.uuid(),
      title: `[BUG] ${faker.lorem.sentence()}`,
      description: faker.lorem.paragraphs(2),
      severity:
        options.severity ??
        faker.helpers.arrayElement(['low', 'medium', 'high', 'critical']),
      status: options.status ?? 'open',
      assigneeId: options.assigneeId,
      stepsToReproduce: Array.from(
        { length: faker.number.int({ min: 2, max: 5 }) },
        (_, i) => `${i + 1}. ${faker.lorem.sentence()}`
      ),
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: DefectFactoryOptions = {}
  ): Defect[] {
    return Array.from({ length: count }, () => this.create(options));
  }
}
