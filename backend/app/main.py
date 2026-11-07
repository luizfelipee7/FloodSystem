"""Local HTTP entry point: uvicorn backend.app.main:app."""

import logging
import sqlite3
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api.v1.routes.telemetry import router
from .api.v1.routes.analytics import router as analytics_router
from .api.v1.routes.experiments import router as experiments_router
from .core.config import Settings
from .core.database import connection, initialize_database
from .repositories.telemetry import DeviceNotFound, DuplicateConflict, TelemetryRepository

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if configuration.enable_article_simulations:
            from .repositories.experiments import check_experiment_database
            check_experiment_database(configuration)
        initialize_database(configuration)
        application.state.repository = TelemetryRepository(configuration)
        yield

    application = FastAPI(title="FloodSystem API", version="0.4.0", lifespan=lifespan,
                          description="Telemetria e cálculos de chuva, nível e velocidade por período. Horários UTC.")
    application.state.settings = configuration
    application.include_router(router)
    application.include_router(analytics_router)
    application.include_router(experiments_router)

    @application.get("/health", tags=["Estado"])
    def health():
        with connection(configuration) as db:
            db.execute("SELECT device_id FROM devices LIMIT 1").fetchone()
        return {"status": "ok", "database": "ok"}

    @application.get("/api/v1/time", tags=["Estado"])
    def server_time():
        """UTC server clock for devices that timestamp events before sending."""
        return {"unix_ms": time.time_ns() // 1_000_000}

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Exclude raw input and exception context: NaN/Infinity cannot be emitted as JSON.
        details = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": details})

    @application.exception_handler(DeviceNotFound)
    async def unknown_device(_request: Request, exc: DeviceNotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(DuplicateConflict)
    async def conflict(_request: Request, exc: DuplicateConflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(ValueError)
    async def invalid_value(_request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(sqlite3.OperationalError)
    async def unavailable_database(_request: Request, exc: sqlite3.OperationalError):
        logger.error("Falha operacional do SQLite: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Banco temporariamente indisponível. Reenvie com os mesmos identificadores."}, headers={"Retry-After": "5"})

    return application


app = create_app()
