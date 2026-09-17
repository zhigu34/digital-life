import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app import admin, auth, checkins, imports, maintenance, records, stats
from app.config import Settings
from app.database import make_engine, migrate, session_factory
from app.models import Base
from app.shows.metadata import router as shows_metadata_router
from app.shows.router import router as shows_router

logger = logging.getLogger(__name__)


def create_app(data_dir=None):
    settings = Settings.from_env(data_dir)

    @asynccontextmanager
    async def lifespan(app):
        migrate(settings)
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="Digital Life", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.engine = make_engine(settings)
    app.state.session_factory = session_factory(app.state.engine)

    @app.middleware("http")
    async def origin_and_cache(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            local_origin = f"{request.url.scheme}://{request.url.netloc}"
            if origin is not None and origin not in {local_origin, *settings.trusted_origins}:
                return JSONResponse(
                    {"detail": "请求来源不受信任"},
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            if request.url.path.endswith("/poster"):
                response.headers["Cache-Control"] = "private, max-age=604800"
            else:
                response.headers["Cache-Control"] = "no-store"
                response.headers["Vary"] = "Cookie"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        try:
            with app.state.engine.connect() as connection:
                for table in Base.metadata.sorted_tables:
                    connection.execute(select(table).limit(1))
                connection.execute(text("SELECT version_num FROM alembic_version"))
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(admin.router)
    # Static show routes must be matched before /api/shows/{item_id}.
    app.include_router(shows_metadata_router)
    app.include_router(shows_router)
    app.include_router(records.router)
    app.include_router(maintenance.router)
    app.include_router(stats.router)
    app.include_router(checkins.router)
    app.include_router(imports.router)
    return app


app = create_app()
