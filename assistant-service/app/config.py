import os

DB_URL = os.getenv("ASSISTANT_DB_URL", "")
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://karenseir-search:8080")
SEARCH_TIMEOUT_SECONDS = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "12"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
BUILD_COMMIT = os.getenv("GIT_COMMIT", "unknown")
SERVICE_VERSION = "0.1.0"
