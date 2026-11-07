from typing import Annotated

from fastapi import Depends, Request

from ..repositories.telemetry import TelemetryRepository


def repository(request: Request) -> TelemetryRepository:
    return request.app.state.repository


Repository = Annotated[TelemetryRepository, Depends(repository)]
