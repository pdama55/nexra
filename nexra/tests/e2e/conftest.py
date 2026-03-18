"""Shared fixtures for E2E tests — same setup as integration."""

import os

import asyncpg
import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import get_settings
from models import Base

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test"),
)
TEST_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")

_tables_created = False


def _asyncpg_dsn(sqlalchemy_url: str) -> str:
    if sqlalchemy_url.startswith("postgresql+asyncpg://"):
        return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return sqlalchemy_url


async def _ensure_database_ready() -> None:
    try:
        conn = await asyncpg.connect(_asyncpg_dsn(TEST_DATABASE_URL), timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(
            "E2E DB is not reachable. "
            "Set TEST_DATABASE_URL (or DATABASE_URL) or run "
            "`./scripts/run_db_backed_tests.sh --infra-mode external --prepare-only`. "
            f"target={TEST_DATABASE_URL} error={exc}"
        )
    else:
        await conn.close()


async def _ensure_redis_ready() -> None:
    client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        pong = await client.ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(
            "E2E Redis is not reachable. "
            "Set REDIS_URL or run "
            "`./scripts/run_db_backed_tests.sh --infra-mode external --prepare-only`. "
            f"target={TEST_REDIS_URL} error={exc}"
        )
    else:
        if pong is not True:
            pytest.skip(f"E2E Redis ping did not return True: target={TEST_REDIS_URL} pong={pong}")
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    global _tables_created
    await _ensure_database_ready()
    await _ensure_redis_ready()
    os.environ["SECRET_KEY_ENCRYPTION_KEY"] = "a" * 64
    get_settings.cache_clear()
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)

    if not _tables_created:
        async with engine.begin() as conn:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    """
                    CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS TRIGGER AS $$
                    BEGIN
                        RAISE EXCEPTION 'audit_log rows are immutable - no UPDATE or DELETE permitted';
                    END;
                    $$ LANGUAGE plpgsql;
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    DROP TRIGGER IF EXISTS enforce_audit_immutability ON audit_log;
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TRIGGER enforce_audit_immutability
                    BEFORE UPDATE OR DELETE ON audit_log
                    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
                    """
                )
            )
        _tables_created = True

    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
