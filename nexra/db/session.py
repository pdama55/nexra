from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings


def create_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=(settings.environment == "development"),
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine = create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
