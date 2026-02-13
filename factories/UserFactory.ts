/**
 * User Factory
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 2 - User factory creates users with roles (admin, member, viewer)
 * AC: 8 - Factories support associations (user belongs to organization)
 */

import { faker } from '@faker-js/faker';
import { User, UserRole } from '../types/entities';

export interface UserFactoryOptions {
  id?: string;
  organizationId?: string;
  role?: UserRole;
  email?: string;
  firstName?: string;
  lastName?: string;
  isActive?: boolean;
}

export class UserFactory {
  static create(options: UserFactoryOptions = {}): User {
    return {
      id: options.id ?? faker.string.uuid(),
      email: options.email ?? faker.internet.email().toLowerCase(),
      firstName: options.firstName ?? faker.person.firstName(),
      lastName: options.lastName ?? faker.person.lastName(),
      role: options.role ?? 'member',
      organizationId: options.organizationId ?? faker.string.uuid(),
      isActive: options.isActive ?? true,
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(count: number, options: UserFactoryOptions = {}): User[] {
    return Array.from({ length: count }, () => this.create(options));
  }

  static createAdmin(options: Omit<UserFactoryOptions, 'role'> = {}): User {
    return this.create({ ...options, role: 'admin' });
  }

  static createViewer(options: Omit<UserFactoryOptions, 'role'> = {}): User {
    return this.create({ ...options, role: 'viewer' });
  }
}
