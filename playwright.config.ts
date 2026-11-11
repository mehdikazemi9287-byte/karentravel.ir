import { defineConfig, devices } from '@playwright/test';
import { randomBytes } from 'crypto';
import { tmpdir } from 'os';
import { join } from 'path';

const e2eDatabase = join(tmpdir(), `karenseir-e2e-${Date.now()}.sqlite`);
const e2ePython = process.env.E2E_PYTHON || '.venv/bin/python';
// Ports are overridable so parallel local runs never collide; CI uses the defaults.
const apiPort = process.env.E2E_API_PORT || '8100';
const webPort = process.env.E2E_WEB_PORT || '3101';
const searchPort = process.env.E2E_SEARCH_PORT || '8102';
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const webOrigin = `http://127.0.0.1:${webPort}`;
const searchOrigin = `http://127.0.0.1:${searchPort}`;
// The frontend searches through /search/v3, which the API forwards to the karenseir-search
// service; that service reads offers back from the API with a shared internal token.
const searchToken = randomBytes(24).toString('hex');
process.env.E2E_API_URL ||= apiOrigin; // specs read this; workers inherit the runner env

export default defineConfig({
  testDir: './e2e',
  // next dev compiles each route on first visit. On shared CI runners two workers competing for that
  // compile made a different set of navigations time out on every run, so CI runs one worker with
  // more room and one retry; local runs keep the strict defaults.
  timeout: process.env.CI ? 90_000 : 30_000,
  expect: { timeout: process.env.CI ? 25_000 : 10_000 },
  fullyParallel: false,
  workers: process.env.CI ? 1 : undefined,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: { baseURL: webOrigin, trace: 'retain-on-failure', ...devices['Desktop Chrome'], channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' },
  webServer: [
    {
      command: `DATABASE_URL=sqlite:///${e2eDatabase} ENVIRONMENT=development PAYMENT_PROVIDER=sandbox SANDBOX_PAYMENT_BASE_URL=${apiOrigin} CORS_ORIGINS=${webOrigin} SEARCH_SERVICE_URL=${searchOrigin} SEARCH_INTERNAL_TOKEN=${searchToken} ${e2ePython} -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiOrigin}/ready`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `MONOLITH_BASE_URL=${apiOrigin} SEARCH_INTERNAL_TOKEN=${searchToken} ENVIRONMENT=development ${e2ePython} -m uvicorn app.main:app --app-dir search-service --host 127.0.0.1 --port ${searchPort}`,
      url: `${searchOrigin}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `NEXT_PUBLIC_API_URL=${apiOrigin} npm run dev -- --webpack --hostname 127.0.0.1 --port ${webPort}`,
      url: webOrigin,
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
