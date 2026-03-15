import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import get_settings
from services.anomaly_service import AnomalyService
from workers.celery_app import celery_app

logger = logging.getLogger("nexra.workers.anomaly")


@celery_app.task(bind=True)
def run_anomaly_detection(self):
    """Hourly Celery beat task for spend anomaly detection."""
    asyncio.run(_detect())


async def _detect():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = AnomalyService(session)
        anomalies = await service.detect_spend_anomalies()
        logger.info(f"Anomaly detection complete: {len(anomalies)} anomalies found")

    await engine.dispose()
