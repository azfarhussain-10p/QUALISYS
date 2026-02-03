// Jest Root Configuration
// Story: 0-10 Automated Test Execution on PR
// AC: 1, 3, 5, 7
// Coverage thresholds, retry logic, project-based test discovery

/** @type {import('jest').Config} */
module.exports = {
  // Project-based test discovery — each service runs its own tests
  projects: [
    {
      displayName: 'api-unit',
      testMatch: ['<rootDir>/api/__tests__/unit/**/*.test.[jt]s?(x)'],
      transform: {
        '^.+\\.tsx?$': 'ts-jest',
      },
      moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
    },
    {
      displayName: 'api-integration',
      testMatch: ['<rootDir>/api/__tests__/integration/**/*.test.[jt]s?(x)'],
      transform: {
        '^.+\\.tsx?$': 'ts-jest',
      },
      moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
    },
    {
      displayName: 'web-unit',
      testMatch: ['<rootDir>/web/__tests__/unit/**/*.test.[jt]s?(x)'],
      testEnvironment: 'jsdom',
      transform: {
        '^.+\\.tsx?$': 'ts-jest',
      },
      moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
    },
  ],

  // Coverage configuration (AC3: 80% target)
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'text-summary', 'lcov', 'cobertura'],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  coveragePathIgnorePatterns: [
    '/node_modules/',
    '/__tests__/',
    '/dist/',
    '/coverage/',
    '/.next/',
    '/e2e/',
  ],

  // Parallel execution (AC5: <10 min target)
  maxWorkers: process.env.CI ? '50%' : '75%',

  // Flaky test retry (AC7: retry 3x before marking failed)
  retryTimes: process.env.CI ? 3 : 0,

  // JUnit reporter for CI (feeds dorny/test-reporter)
  reporters: [
    'default',
    ...(process.env.CI
      ? [['jest-junit', {
          outputDirectory: 'test-results',
          outputName: 'junit.xml',
          classNameTemplate: '{classname}',
          titleTemplate: '{title}',
          ancestorSeparator: ' > ',
        }]]
      : []),
  ],

  // Test timeout
  testTimeout: 30000,
};
