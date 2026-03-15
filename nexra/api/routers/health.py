from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from api.dependencies import get_redis
from db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Health check endpoint. No authentication required.

    Returns 200 if all dependencies reachable, 503 if any are down.
    """
    components = {}
    all_healthy = True

    try:
        await db.execute(text("SELECT 1"))
        components["postgres"] = "healthy"
    except Exception as e:
        components["postgres"] = f"unhealthy: {str(e)[:100]}"
        all_healthy = False

    try:
        await redis_client.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {str(e)[:100]}"
        all_healthy = False

    status_code = 200 if all_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "components": components,
        },
    )
