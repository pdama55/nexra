import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import get_settings
from services.hitl_service import HiTLService
from workers.celery_app import celery_app

logger = logging.getLogger("nexra.workers.hitl")


@celery_app.task(bind=True)
def expire_stale_approvals(self):
    """Periodic task to expire stale HiTL approval requests."""
    asyncio.run(_expire())


async def _expire():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = HiTLService(session)
        count = await service.expire_stale()
        logger.info(f"Expired {count} stale approvals")

    await engine.dispose()
