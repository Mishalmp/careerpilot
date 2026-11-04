from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from careerpilot import health
from careerpilot.core.config import Settings, get_settings
from careerpilot.core.db import create_engine, create_sessionmaker
from careerpilot.core.errors import register_error_handlers
from careerpilot.core.logging import configure_logging
from careerpilot.core.middleware import OriginCheckMiddleware, RequestContextMiddleware
from careerpilot.modules.auth.router import router as auth_router
from careerpilot.modules.auth.throttle import LoginThrottle
from careerpilot.modules.prep.router import router as prep_router
from careerpilot.modules.today.router import router as today_router
from careerpilot.modules.tracker.router import router as tracker_router

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # The engine connects lazily, so building the app never needs a running database.
    engine = create_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await engine.dispose()

    app = FastAPI(title="CareerPilot", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.login_throttle = LoginThrottle(
        settings.login_max_failures, settings.login_window_seconds
    )

    # Last added is outermost: host check, then request context, then origin check.
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(tracker_router, prefix=API_PREFIX)
    app.include_router(prep_router, prefix=API_PREFIX)
    app.include_router(today_router, prefix=API_PREFIX)
    return app


def app_factory() -> FastAPI:
    """Entry point for `uvicorn careerpilot.main:app_factory --factory`."""
    return create_app()
