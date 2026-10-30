from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from fastapi import FastAPI
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import create_database_engine, create_session_factory
from ..service import RetrievalService
from .v1 import router as v1_router


def create_app(
    settings: Settings | None = None,
    service: RetrievalService | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app_settings.validate_auth(require_postgresql=session_factory is None)
        engine = None
        retrieval_service = None
        try:
            if session_factory is None:
                engine = create_database_engine(app_settings.database_url)
                app.state.session_factory = create_session_factory(engine)
            else:
                app.state.session_factory = session_factory
            retrieval_service = service or RetrievalService(app_settings)
            app.state.retrieval_service = retrieval_service
            yield
        finally:
            try:
                if retrieval_service is not None:
                    retrieval_service.close()
            finally:
                if engine is not None:
                    engine.dispose()

    application = FastAPI(title=app_settings.application_name, lifespan=lifespan)
    application.state.settings = app_settings
    application.include_router(v1_router, prefix=app_settings.api_prefix)
    return application


app = create_app()
