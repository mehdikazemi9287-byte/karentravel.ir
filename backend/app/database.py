from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import read_secret


class Base(DeclarativeBase):
    pass


DATABASE_URL = read_secret("DATABASE_URL", "sqlite:///./karenseir.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def set_tenant_context(session, tenant_id: int) -> None:
    """Bind the signed tenant claim to the current PostgreSQL transaction."""
    if tenant_id <= 0:
        raise ValueError("tenant_id must be positive")
    session.info["tenant_id"] = tenant_id
    if session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})


@event.listens_for(Session, "after_begin")
def _restore_tenant_context(session, transaction, connection) -> None:
    tenant_id = session.info.get("tenant_id")
    if tenant_id and connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
