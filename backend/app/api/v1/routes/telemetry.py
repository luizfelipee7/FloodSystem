from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from ...dependencies import Repository
from ...device_auth import require_device_auth
from ....schemas.telemetry import (
    LevelPage, LevelReading, LevelReadingInput, LevelWriteResult, PeriodQuery,
    RainBatchInput, RainBatchResult, RainPage, RainTip, Identifier,
)

router = APIRouter(prefix="/api/v1", tags=["Telemetria"])


@router.post("/level-readings", response_model=LevelWriteResult, status_code=201,
             responses={200: {"model": LevelWriteResult, "description": "Leitura já armazenada"},
                        404: {"description": "Dispositivo não cadastrado"},
                        409: {"description": "Identificador utilizado com conteúdo diferente"}})
def receive_level(payload: LevelReadingInput, response: Response, repo: Repository, request: Request):
    require_device_auth(request, payload.device_id)
    result = repo.save_level_reading(payload.device_id, payload.reading_id,
                                    measured_at=payload.measured_at, distance_cm=payload.distance_cm)
    if not result.created:
        response.status_code = 200
    return {"created": result.created, "reading": result.record}


@router.post("/rain-tips", response_model=RainBatchResult,
             responses={404: {"description": "Dispositivo não cadastrado"},
                        409: {"description": "Conflito: nenhuma nova basculada do lote foi gravada"}})
def receive_rain(payload: RainBatchInput, repo: Repository, request: Request):
    require_device_auth(request, payload.device_id)
    results = repo.save_rain_tips(payload.device_id, [(event.event_id, event.occurred_at) for event in payload.events])
    inserted = sum(result.created for result in results)
    return {
        "inserted_count": inserted,
        "duplicate_count": len(results) - inserted,
        "results": [{"created": result.created, "event": result.record} for result in results],
    }


def page_result(period, items):
    return {
        "device_id": period.device_id, "start": period.start, "end": period.end,
        "limit": period.limit, "offset": period.offset,
        "has_more": len(items) > period.limit, "items": items[:period.limit],
    }


@router.get("/level-readings", response_model=LevelPage)
def query_levels(period: Annotated[PeriodQuery, Query()], repo: Repository):
    items = repo.list_level_readings(period.device_id, start=period.start, end=period.end,
                                    limit=period.limit + 1, offset=period.offset)
    return page_result(period, items)


@router.get("/rain-tips", response_model=RainPage)
def query_rain(period: Annotated[PeriodQuery, Query()], repo: Repository):
    items = repo.list_rain_tips(period.device_id, start=period.start, end=period.end,
                              limit=period.limit + 1, offset=period.offset)
    return page_result(period, items)


@router.get("/rain-tips/latest", response_model=RainTip | None)
def latest_rain_tip(device_id: Annotated[Identifier, Query()], repo: Repository):
    return repo.latest_rain_tip(device_id)


@router.get("/level-readings/latest", response_model=LevelReading | None)
def latest_level_reading(device_id: Annotated[Identifier, Query()], repo: Repository):
    return repo.latest_level_reading(device_id)
