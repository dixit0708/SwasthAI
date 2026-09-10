// Test-only Playwright config for the diabetes E2E suite.
// Assumes the frontend static server (http://127.0.0.1:5500) and backend
// (http://127.0.0.1:8000) are already running — see tests/e2e/README.md.
// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1, // avoid cross-project resource contention causing spurious "not stable" clicks
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5500',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // The site's own Lenis smooth-scroll (js/main.js) already skips itself
    // when prefers-reduced-motion is set (AGENTS.md Section 25) — enabling
    // it here avoids Playwright's auto-scroll-before-click fighting Lenis's
    // eased scroll animation, without touching any application file.
    reducedMotion: 'reduce',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'mobile-390',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } },
    },
    {
      name: 'mobile-320',
      use: { ...devices['Desktop Chrome'], viewport: { width: 320, height: 720 } },
    },
  ],
});
