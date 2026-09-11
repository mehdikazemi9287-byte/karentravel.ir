import os

DB_URL = os.getenv("ASSISTANT_DB_URL", "")
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://karenseir-search:8080")
SEARCH_TIMEOUT_SECONDS = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "12"))
# Phase 4: real reservation/hold wiring. Every call is made with the
# CALLER-forwarded user's own Bearer token (see tools.py) -- this service
# never mints or holds a service-account credential for the monolith.
MONOLITH_BASE_URL = os.getenv("MONOLITH_BASE_URL", "http://karenseir-api-1:8000")
MONOLITH_TIMEOUT_SECONDS = float(os.getenv("MONOLITH_TIMEOUT_SECONDS", "12"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
BUILD_COMMIT = os.getenv("GIT_COMMIT", "unknown")
SERVICE_VERSION = "0.1.0"
