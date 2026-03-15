import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.errors import NexraError


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Nexra API",
        description="The control plane for AI agent networks",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )

    # ── Middleware ──
    from api.middleware.logging import RequestLoggingMiddleware

    app.add_middleware(RequestLoggingMiddleware)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Exception Handlers ──
    @app.exception_handler(NexraError)
    async def nexra_error_handler(request: Request, exc: NexraError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    # ── Routers ──
    from api.routers.health import router as health_router

    app.include_router(health_router)

    from api.routers.orgs import router as orgs_router

    app.include_router(orgs_router, prefix="/v1")

    from api.routers.agents import router as agents_router

    app.include_router(agents_router, prefix="/v1")

    from api.routers.capabilities import router as capabilities_router

    app.include_router(capabilities_router, prefix="/v1")

    from api.routers.policies import router as policies_router

    app.include_router(policies_router, prefix="/v1")

    from api.routers.delegations import router as delegations_router

    app.include_router(delegations_router, prefix="/v1")

    from api.routers.audit import router as audit_router

    app.include_router(audit_router, prefix="/v1")

    from api.routers.analytics import router as analytics_router

    app.include_router(analytics_router, prefix="/v1")

    from api.routers.siem import router as siem_router

    app.include_router(siem_router, prefix="/v1")

    from api.routers.compliance import router as compliance_router

    app.include_router(compliance_router, prefix="/v1")

    from api.routers.marketplace import router as marketplace_router

    app.include_router(marketplace_router, prefix="/v1")

    # ── Lifecycle ──
    from api.dependencies import close_redis

    @app.on_event("shutdown")
    async def shutdown():
        await close_redis()

    # ── Sentry ──
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1 if settings.environment == "production" else 1.0,
            environment=settings.environment,
        )

    return app


app = create_app()
