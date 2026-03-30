import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: ['scripts/**/*.js'],
  timeout: 600_000,
  fullyParallel: false,
  reporter: 'line',
  use: {
    trace: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});