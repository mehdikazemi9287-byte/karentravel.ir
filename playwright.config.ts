import { defineConfig, devices } from '@playwright/test';

const e2eDatabase = `/private/tmp/karenseir-e2e-${Date.now()}.sqlite`;
const e2ePython = process.env.E2E_PYTHON || '.venv/bin/python';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:3100', trace: 'retain-on-failure', ...devices['Desktop Chrome'], channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' },
  webServer: [
    {
      command: `DATABASE_URL=sqlite:///${e2eDatabase} ENVIRONMENT=development CORS_ORIGINS=http://127.0.0.1:3100 ${e2ePython} -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8100`,
      url: 'http://127.0.0.1:8100/ready',
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --webpack --hostname 127.0.0.1 --port 3100',
      url: 'http://127.0.0.1:3100',
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
