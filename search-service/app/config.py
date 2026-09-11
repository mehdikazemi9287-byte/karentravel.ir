import os

MONOLITH_BASE_URL = os.getenv("MONOLITH_BASE_URL", "http://karenseir-api-1:8000")
INTERNAL_TOKEN = os.getenv("SEARCH_INTERNAL_TOKEN", "")
REDIS_URL = os.getenv("SEARCH_REDIS_URL", "")           # e.g. redis://karenseir-redis:6379/1
TELEMETRY_DB_URL = os.getenv("SEARCH_TELEMETRY_DB_URL", "")   # Search-owned Postgres DB, separate from the monolith DB
PROVIDER_TIMEOUT_SECONDS = float(os.getenv("SEARCH_PROVIDER_TIMEOUT", "6"))
TOTAL_TIMEOUT_SECONDS = float(os.getenv("SEARCH_TOTAL_TIMEOUT", "12"))
MAX_CONCURRENCY = int(os.getenv("SEARCH_MAX_CONCURRENCY", "6"))
CACHE_TTL_SECONDS = int(os.getenv("SEARCH_CACHE_TTL", "45"))
AUTOCOMPLETE_CACHE_TTL = int(os.getenv("SEARCH_AUTOCOMPLETE_TTL", "300"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
BUILD_COMMIT = os.getenv("GIT_COMMIT", "unknown")
BUILD_TIME = os.getenv("BUILD_TIMESTAMP", "unknown")
SERVICE_VERSION = "1.0.0"
