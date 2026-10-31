import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_karenseir.db")
os.environ.setdefault("ENVIRONMENT", "development")
# The shared test DB reuses accounts; the per-account SMS throttle has its own dedicated test.
os.environ.setdefault("OTP_RESEND_COOLDOWN_SECONDS", "0")
os.environ.setdefault("OTP_MAX_PER_HOUR", "100000")

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
