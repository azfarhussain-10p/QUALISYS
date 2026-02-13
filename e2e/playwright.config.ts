// Playwright E2E Test Configuration
// Story: 0-10 Automated Test Execution on PR
// Story: 0-17 Test Reporting Dashboard (Allure reporter)
// AC: 1, 5, 7
// Critical-path E2E tests on PR, full suite in nightly, Allure reporting

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // Test directories
  testDir: './tests',

  // Timeouts
  timeout: 30_000,
  expect: { timeout: 5_000 },

  // Parallel execution (AC5: <10 min target)
  fullyParallel: true,
  workers: process.env.CI ? 2 : undefined,

  // Flaky test retry (AC7: retry failed tests before marking failed)
  retries: process.env.CI ? 2 : 0,

  // Fail fast in CI — stop after first failure shard
  forbidOnly: !!process.env.CI,

  // Reporters — JUnit for CI test-reporter, HTML for local debugging, Allure for dashboard (Story 0-17)
  reporter: process.env.CI
    ? [
        ['list'],
        ['junit', { outputFile: 'test-results/e2e-results.xml' }],
        ['html', { open: 'never', outputFolder: 'playwright-report' }],
        ['allure-playwright', { outputFolder: 'allure-results', suiteTitle: 'E2E Tests' }],
      ]
    : [
        ['list'],
        ['html', { open: 'on-failure', outputFolder: 'playwright-report' }],
      ],

  // Shared settings for all projects
  use: {
    // Base URL — override via PLAYWRIGHT_BASE_URL env var
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',

    // Evidence capture on failure
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',

    // Headless in CI
    headless: true,
  },

  // Browser projects
  projects: [
    // Critical path tests — run on every PR (AC1)
    {
      name: 'chromium-critical',
      testDir: './tests/critical',
      use: { ...devices['Desktop Chrome'] },
    },
    // Full suite — nightly or manual trigger only
    {
      name: 'chromium-full',
      testDir: './tests/full',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox-full',
      testDir: './tests/full',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit-full',
      testDir: './tests/full',
      use: { ...devices['Desktop Safari'] },
    },
  ],

  // Dev server — start app before running tests (local only)
  // Uncomment when application code exists:
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:3000',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120_000,
  // },
});
