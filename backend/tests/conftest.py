import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_karenseir.db")
os.environ.setdefault("ENVIRONMENT", "development")

from app.main import Base, SessionLocal, app, engine, seed

def pytest_sessionstart(session):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
