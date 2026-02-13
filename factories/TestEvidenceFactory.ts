/**
 * Test Evidence Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 6 - Test execution factory creates execution records (evidence supports executions)
 */

import { faker } from '@faker-js/faker';
import { TestEvidence } from '../types/entities';

export interface TestEvidenceFactoryOptions {
  id?: string;
  executionId?: string;
  type?: TestEvidence['type'];
}

export class TestEvidenceFactory {
  static create(options: TestEvidenceFactoryOptions = {}): TestEvidence {
    const type =
      options.type ??
      faker.helpers.arrayElement([
        'screenshot',
        'video',
        'log',
        'har',
      ] as const);

    const extensions: Record<TestEvidence['type'], string> = {
      screenshot: 'png',
      video: 'webm',
      log: 'txt',
      har: 'har',
    };

    return {
      id: options.id ?? faker.string.uuid(),
      executionId: options.executionId ?? faker.string.uuid(),
      type,
      filePath: `evidence/${faker.string.uuid()}.${extensions[type]}`,
      fileSize: faker.number.int({ min: 1024, max: 10485760 }),
      caption: faker.datatype.boolean() ? faker.lorem.sentence() : undefined,
      createdAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: TestEvidenceFactoryOptions = {}
  ): TestEvidence[] {
    return Array.from({ length: count }, () => this.create(options));
  }
}
