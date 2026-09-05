from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies.settings import SETTINGS_STATE_KEY
from src.api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from src.api.routes import analyses, health, notes, reviews, users
from src.core.config import Settings, get_settings
from src.core.exception_handlers import register_exception_handlers
from src.core.logger import configure_logging, get_logger

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = getattr(app.state, SETTINGS_STATE_KEY)
    settings.validate_runtime_readiness()
    get_logger(__name__).info(
        "application_started",
        extra={"environment": settings.environment.value, "provider": settings.llm_provider.value},
    )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Note Insight API",
        version=settings.api_version,
        # Disabling the docs UI while still serving the schema it renders would
        # hide nothing: /openapi.json is the API surface in machine-readable
        # form. Both go together.
        docs_url=None if settings.is_production else "/docs",
        openapi_url=None if settings.is_production else "/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    setattr(app.state, SETTINGS_STATE_KEY, settings)

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(notes.router, prefix=API_PREFIX)
    app.include_router(analyses.note_scoped_router, prefix=API_PREFIX)
    app.include_router(analyses.analysis_router, prefix=API_PREFIX)
    app.include_router(reviews.router, prefix=API_PREFIX)

    return app


app = create_app()
