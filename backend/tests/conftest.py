import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_karenseir.db")
os.environ.setdefault("ENVIRONMENT", "development")

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
