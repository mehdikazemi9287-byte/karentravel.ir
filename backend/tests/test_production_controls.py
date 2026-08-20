import asyncio
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.database import Base
from app.config import read_secret
from app.providers import ProviderContext, ProviderHealth, ResilientAdapter, RetryPolicy, SandboxAdapter, validate_provider_modes
from app.rate_limit import InMemoryRateLimiter, RedisRateLimiter, fingerprint


def test_in_memory_rate_limit_positive_and_negative_paths():
    limiter = InMemoryRateLimiter()
    assert asyncio.run(limiter.hit("test", 2, 60)).allowed
    assert asyncio.run(limiter.hit("test", 2, 60)).allowed
    denied = asyncio.run(limiter.hit("test", 2, 60))
    assert not denied.allowed
    assert denied.retry_after > 0


class FakeRedis:
    def __init__(self): self.count = 0
    async def eval(self, script, keys, key, window):
        self.count += 1
        return [self.count, window]
    async def ping(self): return True


def test_redis_rate_limiter_uses_atomic_counter_contract():
    limiter = RedisRateLimiter(FakeRedis())
    assert limiter.distributed
    assert asyncio.run(limiter.ping())
    assert asyncio.run(limiter.hit("shared", 1, 30)).allowed
    assert not asyncio.run(limiter.hit("shared", 1, 30)).allowed
    assert "bearer-token" not in fingerprint("bearer-token")


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="TEST_REDIS_URL is required for real Redis integration")
def test_real_redis_rate_limit_is_shared_atomic_and_expires():
    limiter = RedisRateLimiter.from_url(os.environ["TEST_REDIS_URL"])
    key = f"karenseir:test:rate-limit:{uuid.uuid4()}"

    async def exercise():
        try:
            assert await limiter.ping()
            assert (await limiter.hit(key, 2, 30)).allowed
            second = await limiter.hit(key, 2, 30)
            denied = await limiter.hit(key, 2, 30)
            assert second.allowed and second.remaining == 0
            assert not denied.allowed and 0 < denied.retry_after <= 30
        finally:
            await limiter.client.delete(key)
            await limiter.client.aclose()

    asyncio.run(exercise())


def test_sandbox_adapter_requires_https_and_secret_reference():
    context = ProviderContext(tenant_id=1, correlation_id="corr", idempotency_key="idem")
    valid = SandboxAdapter("payment", endpoint="https://sandbox.example.test", secret_reference="vault://karenseir/payment")
    assert valid.execute("authorize", {}, context)["ok"] is False
    with pytest.raises(RuntimeError, match="HTTPS"):
        SandboxAdapter("payment", endpoint="http://sandbox.example.test", secret_reference="vault://karenseir/payment").validate_configuration()
    with pytest.raises(RuntimeError, match="secret-manager"):
        SandboxAdapter("otp", endpoint="https://sandbox.example.test", secret_reference="plain-secret").validate_configuration()


class FakeSyncRedis:
    def __init__(self): self.values = {}; self.rate = 0
    def ping(self): return True
    def exists(self, key): return key in self.values
    def eval(self, script, keys, key, window): self.rate += 1; return self.rate
    def incr(self, key): self.values[key] = int(self.values.get(key, 0)) + 1; return self.values[key]
    def expire(self, key, seconds): return True
    def setex(self, key, seconds, value): self.values[key] = value
    def delete(self, *keys):
        for key in keys: self.values.pop(key, None)


class FakeProvider:
    key = "flight"; mode = "sandbox"; timeout_seconds = 1.0
    def __init__(self, failures=0, attempts=3): self.failures = failures; self.calls = 0; self.retry_policy = RetryPolicy(max_attempts=attempts, initial_backoff_seconds=0, max_backoff_seconds=0)
    def validate_configuration(self): return None
    def health(self): return ProviderHealth("ok", self.mode, "test")
    def execute(self, operation, payload, context):
        self.calls += 1
        if self.calls <= self.failures: return {"ok": False, "reason": "temporary", "error": {"retryable": True}}
        return {"ok": True, "status": "accepted"}


def test_provider_resilience_retries_throttles_and_opens_circuit():
    redis = FakeSyncRedis(); provider = FakeProvider(failures=2)
    adapter = ResilientAdapter(provider, redis_url="redis://test", rate_limit=10)
    adapter._redis = redis
    context = ProviderContext(tenant_id=7, correlation_id="corr", idempotency_key="idem")
    assert adapter.execute("search", {}, context)["ok"] is True
    assert provider.calls == 3
    throttled_redis = FakeSyncRedis(); throttled = ResilientAdapter(FakeProvider(), redis_url="redis://test", rate_limit=1); throttled._redis = throttled_redis
    assert throttled.execute("search", {}, context)["ok"] is True
    assert throttled.execute("search", {}, context)["reason"] == "provider_rate_limited"
    circuit_redis = FakeSyncRedis(); failing = ResilientAdapter(FakeProvider(failures=10, attempts=1), redis_url="redis://test", rate_limit=10, failure_threshold=2); failing._redis = circuit_redis
    assert failing.execute("book", {}, context)["ok"] is False
    assert failing.execute("book", {}, context)["ok"] is False
    assert failing.execute("book", {}, context)["reason"] == "provider_circuit_open"


def test_secret_file_is_read_only_with_private_permissions(tmp_path, monkeypatch):
    secret_file = tmp_path / "jwt"
    secret_file.write_text("mounted-secret\n", encoding="utf-8")
    secret_file.chmod(0o600)
    monkeypatch.delenv("TEST_SECRET", raising=False)
    monkeypatch.setenv("TEST_SECRET_FILE", str(secret_file))
    assert read_secret("TEST_SECRET") == "mounted-secret"


def test_secret_file_rejects_conflict_unsafe_permissions_and_symlink(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret"
    secret_file.write_text("secret", encoding="utf-8")
    secret_file.chmod(0o644)
    monkeypatch.setenv("TEST_SECRET_FILE", str(secret_file))
    with pytest.raises(RuntimeError, match="permissions"):
        read_secret("TEST_SECRET")
    secret_file.chmod(0o600)
    monkeypatch.setenv("TEST_SECRET", "inline")
    with pytest.raises(RuntimeError, match="cannot both"):
        read_secret("TEST_SECRET")
    monkeypatch.delenv("TEST_SECRET")
    link = tmp_path / "link"
    link.symlink_to(secret_file)
    monkeypatch.setenv("TEST_SECRET_FILE", str(link))
    with pytest.raises(RuntimeError, match="non-symlink"):
        read_secret("TEST_SECRET")


def test_production_mock_provider_requires_explicit_demo_mode(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER_MODE", "mock")
    with pytest.raises(RuntimeError, match="forbidden"):
        validate_provider_modes("production", False, ("payment",))
    validate_provider_modes("production", True, ("payment",))
    validate_provider_modes("development", False, ("payment",))


def test_every_metadata_tenant_table_is_discoverable_for_rls():
    tenant_tables = {table.name for table in Base.metadata.sorted_tables if "tenant_id" in table.c}
    assert tenant_tables
    assert {"users", "bookings", "reservations", "trips", "outbox_events"}.issubset(tenant_tables)


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is required for destructive isolated PostgreSQL RLS verification")
def test_postgresql_rls_allows_own_tenant_and_denies_cross_tenant():
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    with engine.begin() as connection:
        assert connection.dialect.name == "postgresql"
        connection.execute(text("SELECT set_config('app.tenant_id', '1', true)"))
        assert set(connection.execute(text("SELECT DISTINCT tenant_id FROM users")).scalars()) <= {1}
        with pytest.raises(DBAPIError):
            connection.execute(text("INSERT INTO users (tenant_id, email, name, role) VALUES (2, 'rls-negative@test.invalid', 'negative', 'employee')"))
    with engine.begin() as connection:
        connection.execute(text("SELECT set_config('app.tenant_id', '2', true)"))
        assert set(connection.execute(text("SELECT DISTINCT tenant_id FROM users")).scalars()) <= {2}


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is required for PostgreSQL RLS mutation verification")
def test_postgresql_rls_blocks_missing_context_and_cross_tenant_updates():
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    marker = "rls-own-tenant@test.invalid"
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 0
        connection.execute(text("SELECT set_config('app.tenant_id', '1', true)"))
        created_id = connection.scalar(text("INSERT INTO users (tenant_id, email, name, role) VALUES (1, :email, 'RLS own tenant', 'employee') RETURNING id"), {"email": marker})
        assert created_id is not None
        cross_tenant = connection.execute(text("UPDATE users SET name='forbidden' WHERE tenant_id=2"))
        assert cross_tenant.rowcount == 0
        own_tenant = connection.execute(text("UPDATE users SET name='allowed' WHERE id=:id"), {"id": created_id})
        assert own_tenant.rowcount == 1
        connection.execute(text("DELETE FROM users WHERE id=:id"), {"id": created_id})


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is required for PostgreSQL RLS policy verification")
def test_postgresql_all_tenant_tables_force_rls():
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    with engine.connect() as connection:
        tenant_tables = set(connection.execute(text("SELECT table_name FROM information_schema.columns WHERE table_schema='public' AND column_name='tenant_id'")).scalars())
        protected = set(connection.execute(text("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relrowsecurity AND c.relforcerowsecurity")).scalars())
        policies = set(connection.execute(text("SELECT tablename FROM pg_policies WHERE schemaname='public' AND policyname='karenseir_tenant_isolation'")).scalars())
        assert tenant_tables
        assert tenant_tables <= protected
        assert tenant_tables <= policies


@pytest.mark.skipif(not os.getenv("TEST_WORKER_POSTGRES_URL"), reason="TEST_WORKER_POSTGRES_URL is required for worker-role verification")
def test_worker_role_bypasses_rls_but_has_only_outbox_permissions():
    engine = create_engine(os.environ["TEST_WORKER_POSTGRES_URL"])
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user")) is True
        assert connection.scalar(text("SELECT has_table_privilege(current_user, 'outbox_events', 'SELECT,UPDATE')")) is True
        assert connection.scalar(text("SELECT has_table_privilege(current_user, 'notifications', 'SELECT,UPDATE')")) is True
        assert connection.scalar(text("SELECT has_table_privilege(current_user, 'users', 'SELECT')")) is False
        assert connection.scalar(text("SELECT count(*) FROM outbox_events")) >= 0
