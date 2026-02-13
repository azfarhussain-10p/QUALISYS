/**
 * Organization Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 3 - Organization factory creates orgs with tenant schemas
 * AC: 8 - Factories support associations
 */

import { faker } from '@faker-js/faker';
import { Organization, OrgPlan } from '../types/entities';

export interface OrganizationFactoryOptions {
  id?: string;
  name?: string;
  plan?: OrgPlan;
  tenantId?: string;
  schemaName?: string;
}

export class OrganizationFactory {
  static create(options: OrganizationFactoryOptions = {}): Organization {
    const tenantId = options.tenantId ?? faker.string.uuid();
    const name = options.name ?? faker.company.name();
    const plan = options.plan ?? 'free';

    return {
      id: options.id ?? faker.string.uuid(),
      name,
      slug: faker.helpers.slugify(name).toLowerCase(),
      tenantId,
      schemaName:
        options.schemaName ??
        `tenant_${tenantId.replace(/-/g, '_').substring(0, 8)}`,
      plan,
      settings: {
        maxUsers:
          plan === 'enterprise' ? 100 : plan === 'pro' ? 25 : 5,
        maxProjects:
          plan === 'enterprise' ? 50 : plan === 'pro' ? 10 : 2,
      },
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(
    count: number,
    options: OrganizationFactoryOptions = {}
  ): Organization[] {
    return Array.from({ length: count }, () => this.create(options));
  }
}
