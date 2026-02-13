/**
 * Project Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 4 - Project factory creates projects with configurations
 * AC: 8 - Factories support associations (project belongs to organization)
 */

import { faker } from '@faker-js/faker';
import { Project } from '../types/entities';

export interface ProjectFactoryOptions {
  id?: string;
  organizationId?: string;
  name?: string;
  description?: string;
  isActive?: boolean;
}

export class ProjectFactory {
  static create(options: ProjectFactoryOptions = {}): Project {
    return {
      id: options.id ?? faker.string.uuid(),
      name:
        options.name ??
        `${faker.commerce.productAdjective()} ${faker.commerce.product()} Tests`,
      description: options.description ?? faker.lorem.paragraph(),
      organizationId: options.organizationId ?? faker.string.uuid(),
      settings: {
        defaultBrowser: 'chrome',
        parallelExecutions: faker.number.int({ min: 1, max: 10 }),
        retryCount: 2,
      },
      isActive: options.isActive ?? true,
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: ProjectFactoryOptions = {}
  ): Project[] {
    return Array.from({ length: count }, () => this.create(options));
  }
}
