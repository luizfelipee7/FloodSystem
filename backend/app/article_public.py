"""Read-only HTTP entry point for published weather experiments.

This app deliberately mounts only the experiment catalogue, detail and export
routes. The deployment also gives the process read access only to its SQLite.
"""

import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.v1.routes.experiments import router as experiments_router
from .core.config import Settings
from .repositories.experiments import check_experiment_database
from .repositories.telemetry import DeviceNotFound


def create_article_app() -> FastAPI:
    settings = Settings.from_env()
    if not settings.enable_article_simulations:
        raise ValueError("A API pública de ensaios exige o modo científico habilitado.")

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        check_experiment_database(settings)
        if not settings.database_path.is_file():
            raise RuntimeError("O banco científico precisa existir antes de iniciar a API.")
        uri = settings.database_path.as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 2:
                raise RuntimeError("Esquema científico incompatível com esta API.")
        yield

    application = FastAPI(
        title="FloodSystem · Ensaios meteorológicos",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.include_router(experiments_router)

    @application.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok", "purpose": "article-simulations"}

    @application.exception_handler(DeviceNotFound)
    async def unknown_experiment(_request: Request, exc: DeviceNotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(ValueError)
    async def invalid_experiment(_request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return application


app = create_article_app()
