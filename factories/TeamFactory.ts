/**
 * Team Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 8 - Factories support associations (team belongs to organization)
 */

import { faker } from '@faker-js/faker';
import { Team } from '../types/entities';

export interface TeamFactoryOptions {
  id?: string;
  organizationId?: string;
  name?: string;
  memberIds?: string[];
}

export class TeamFactory {
  static create(options: TeamFactoryOptions = {}): Team {
    return {
      id: options.id ?? faker.string.uuid(),
      name: options.name ?? `${faker.commerce.department()} Team`,
      organizationId: options.organizationId ?? faker.string.uuid(),
      memberIds: options.memberIds ?? [],
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: TeamFactoryOptions = {}
  ): Team[] {
    return Array.from({ length: count }, () => this.create(options));
  }
}
