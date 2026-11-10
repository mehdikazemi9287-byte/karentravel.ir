import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_karenseir.db")
os.environ.setdefault("ENVIRONMENT", "development")
# The shared test DB reuses accounts; the per-account SMS throttle has its own dedicated test.
os.environ.setdefault("OTP_RESEND_COOLDOWN_SECONDS", "0")
os.environ.setdefault("OTP_MAX_PER_HOUR", "100000")
# Same for the global per-destination SMS cap (app/sms_guard.py); test_phase1_rest.py tests it with low limits.
os.environ.setdefault("SMS_DEST_MAX_PER_HOUR", "100000")
os.environ.setdefault("SMS_DEST_MAX_PER_DAY", "100000")
# Production stores uploads in /app/media (container volume); CI runners cannot create /app.
if "MEDIA_STORAGE_ROOT" not in os.environ and "MEDIA_STORAGE_ROOT_FILE" not in os.environ:
    import tempfile
    os.environ["MEDIA_STORAGE_ROOT"] = tempfile.mkdtemp(prefix="karenseir-media-")

from app.main import Base, SessionLocal, app, engine, seed

def pytest_sessionstart(session):
    if os.getenv("PRESERVE_MIGRATED_TEST_DATABASE") == "1":
        if not os.getenv("DATABASE_URL", "").startswith("postgresql"):
            raise RuntimeError("PRESERVE_MIGRATED_TEST_DATABASE requires an explicit PostgreSQL DATABASE_URL")
        return
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
