"""Shared fixtures for E2E tests — same setup as integration."""

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test"

_tables_created = False


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    global _tables_created
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)

    if not _tables_created:
        async with engine.begin() as conn:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        _tables_created = True

    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
