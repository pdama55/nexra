import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import get_settings
from services.siem_service import SIEMService
from workers.celery_app import celery_app

logger = logging.getLogger("nexra.workers.siem")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def export_all_siem_events(self):
    """Export org-scoped audit deltas to configured SIEM targets."""
    asyncio.run(_export_all())


async def _export_all():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = SIEMService(session)
        configs = await service.list_enabled_configs()
        for config in configs:
            try:
                exported = await service.export_next_batch(config)
                if exported > 0:
                    logger.info(
                        "Exported %s events for org %s via %s",
                        exported,
                        config.org_id,
                        config.target,
                    )
            except Exception as exc:
                logger.exception(
                    "SIEM export failed for org %s (%s): %s",
                    config.org_id,
                    config.target,
                    exc,
                )

    await engine.dispose()
