from typing import Annotated

from fastapi import APIRouter, Query

from ...dependencies import Repository
from ....schemas.analytics import PeriodSummary, SummaryQuery
from ....services.calculations import period_summary

router = APIRouter(prefix="/api/v1", tags=["Cálculos"])


@router.get("/summary", response_model=PeriodSummary,
            summary="Resumo de chuva e nível por período",
            description="Intervalo [start, end), UTC. Intensidade na janela encerrada em end; "
                        "padrão de 5 minutos. Indicadores sem dados/calibração retornam null e motivo.",
            responses={404: {"description": "Dispositivo não cadastrado"}})
def query_summary(period: Annotated[SummaryQuery, Query()], repo: Repository):
    return period_summary(repo.settings, **period.model_dump())
