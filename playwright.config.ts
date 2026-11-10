import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'os';
import { join } from 'path';

const e2eDatabase = join(tmpdir(), `karenseir-e2e-${Date.now()}.sqlite`);
const e2ePython = process.env.E2E_PYTHON || '.venv/bin/python';
const webStart = process.env.E2E_WEB_MODE === 'start';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:3101', trace: 'retain-on-failure', ...devices['Desktop Chrome'], channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' },
  webServer: [
    {
      command: `DATABASE_URL=sqlite:///${e2eDatabase} ENVIRONMENT=development PAYMENT_PROVIDER=sandbox SANDBOX_PAYMENT_BASE_URL=http://127.0.0.1:8100 CORS_ORIGINS=http://127.0.0.1:3101 ${e2ePython} -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8100`,
      url: 'http://127.0.0.1:8100/ready',
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      // E2E_WEB_MODE=start (CI): production build + `next start`. The dev server compiles each route on first
      // visit, which on shared CI runners made different navigations time out on every run.
      command: webStart
        ? 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run build && npm run start -- --hostname 127.0.0.1 --port 3101'
        : 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --webpack --hostname 127.0.0.1 --port 3101',
      url: 'http://127.0.0.1:3101',
      timeout: webStart ? 600_000 : 120_000,
      reuseExistingServer: false,
    },
  ],
});
