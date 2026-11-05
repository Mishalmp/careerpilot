import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from careerpilot import health
from careerpilot.core.config import Settings, get_settings
from careerpilot.core.db import create_engine, create_sessionmaker
from careerpilot.core.errors import register_error_handlers
from careerpilot.core.fetcher import Fetcher
from careerpilot.core.llm import make_llm
from careerpilot.core.logging import configure_logging
from careerpilot.core.middleware import OriginCheckMiddleware, RequestContextMiddleware
from careerpilot.modules.analytics.router import router as analytics_router
from careerpilot.modules.auth.router import router as auth_router
from careerpilot.modules.auth.throttle import LoginThrottle
from careerpilot.modules.digest.router import router as digest_router
from careerpilot.modules.discovery.router import router as discovery_router
from careerpilot.modules.intel.router import router as intel_router
from careerpilot.modules.knowledge.embeddings import make_embedder
from careerpilot.modules.knowledge.router import router as knowledge_router
from careerpilot.modules.mock.router import router as mock_router
from careerpilot.modules.offers.router import router as offers_router
from careerpilot.modules.outreach.router import router as outreach_router
from careerpilot.modules.practice.router import router as practice_router
from careerpilot.modules.prep.router import router as prep_router
from careerpilot.modules.scoring.router import router as scoring_router
from careerpilot.modules.stories.router import router as stories_router
from careerpilot.modules.tasks.router import router as tasks_router
from careerpilot.modules.today.router import router as today_router
from careerpilot.modules.tracker.router import router as tracker_router
from careerpilot.modules.verification.router import router as verification_router
from careerpilot.worker import worker_loop

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # The engine connects lazily, so building the app never needs a running database.
    engine = create_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        stop = asyncio.Event()
        worker: asyncio.Task[None] | None = None
        if settings.worker_enabled:
            worker = asyncio.create_task(
                worker_loop(app.state.sessionmaker, app.state.fetcher, settings, stop)
            )
        yield
        stop.set()
        if worker is not None:
            await worker
        await engine.dispose()

    app = FastAPI(title="CareerPilot", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.embedder = make_embedder(
        settings.embedder, settings.embedding_model, settings.model_cache_dir
    )
    app.state.llm = make_llm(settings)
    app.state.fetcher = Fetcher()
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
    app.include_router(practice_router, prefix=API_PREFIX)
    app.include_router(knowledge_router, prefix=API_PREFIX)
    app.include_router(verification_router, prefix=API_PREFIX)
    app.include_router(scoring_router, prefix=API_PREFIX)
    app.include_router(outreach_router, prefix=API_PREFIX)
    app.include_router(intel_router, prefix=API_PREFIX)
    app.include_router(mock_router, prefix=API_PREFIX)
    app.include_router(discovery_router, prefix=API_PREFIX)
    app.include_router(tasks_router, prefix=API_PREFIX)
    app.include_router(digest_router, prefix=API_PREFIX)
    app.include_router(analytics_router, prefix=API_PREFIX)
    app.include_router(offers_router, prefix=API_PREFIX)
    app.include_router(stories_router, prefix=API_PREFIX)
    app.include_router(today_router, prefix=API_PREFIX)
    return app


def app_factory() -> FastAPI:
    """Entry point for `uvicorn careerpilot.main:app_factory --factory`."""
    return create_app()
