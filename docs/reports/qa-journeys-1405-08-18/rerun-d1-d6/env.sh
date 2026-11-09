# Local QA re-run stack for D1/D6 (ports 8400 API, 3400 web, 8490 search). Sandbox gateway = test only.
export DATABASE_URL=sqlite:////home/claude/qa-d1run/qa.sqlite ENVIRONMENT=development CORS_ORIGINS=http://127.0.0.1:3400,http://localhost:3400 OTP_RESEND_COOLDOWN_SECONDS=0 OTP_MAX_PER_HOUR=100000 SEARCH_SERVICE_URL=http://127.0.0.1:8490 SEARCH_INTERNAL_TOKEN=qa-local-internal-token-0000000000
export PAYMENT_PROVIDER=sandbox SANDBOX_PAYMENT_BASE_URL=http://127.0.0.1:8400 PUBLIC_WEB_URL=http://127.0.0.1:3400
export MONOLITH_BASE_URL=http://127.0.0.1:8400
export QA_WEB=http://127.0.0.1:3400 QA_API=http://127.0.0.1:8400 QA_DIR=/home/claude/qa-d1run QA_BACKEND=/home/claude/d1fix/backend
