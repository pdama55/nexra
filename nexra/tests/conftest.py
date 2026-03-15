import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:
    """Yields a session wrapped in a SAVEPOINT.

    Each test runs inside a nested transaction (savepoint). After the test,
    the savepoint is rolled back so tests never commit real data and cannot
    interfere with each other.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            nested = await session.begin_nested()
            yield session
            if nested.is_active:
                await nested.rollback()
