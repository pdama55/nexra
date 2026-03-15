from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "nexra",
    broker=settings.celery_broker,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "workers.billing_worker.*": {"queue": "billing"},
        "workers.webhook_worker.*": {"queue": "webhooks"},
        "workers.anomaly_worker.*": {"queue": "anomaly"},
        "workers.hitl_worker.*": {"queue": "hitl"},
        "workers.siem_worker.*": {"queue": "siem"},
    },
    beat_schedule={
        "anomaly-detection-hourly": {
            "task": "workers.anomaly_worker.run_anomaly_detection",
            "schedule": 3600.0,
        },
        "hitl-expiry-hourly": {
            "task": "workers.hitl_worker.expire_stale_approvals",
            "schedule": 3600.0,
        },
    },
)
