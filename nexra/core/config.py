import re
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    openai_api_key: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_delegation_meter_id: str
    secret_key_encryption_key: str

    sentry_dsn: str | None = None
    environment: str = "development"
    log_level: str = "INFO"
    rate_limit_growth_rpm: int = 1000
    rate_limit_starter_rpm: int = 100
    max_delegation_depth_default: int = 5
    webhook_timeout_default_ms: int = 30000
    hil_approval_ttl_hours: int = 24
    anomaly_sigma_threshold: float = 3.0
    celery_broker_url: str | None = None
    api_base_url: str = "http://localhost:8000"

    @field_validator("secret_key_encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", v):
            raise ValueError(
                "secret_key_encryption_key must be exactly 64 hex characters (32 bytes). "
                'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return v

    @property
    def celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
