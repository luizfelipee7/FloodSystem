"""Read-only scientific experiment catalogue and complete artifact export."""

from fastapi import APIRouter, HTTPException, Request, Response

from ....repositories.experiments import experiment_detail, export_experiment, list_experiments

router = APIRouter(prefix="/api/v1/experiments", tags=["Ensaios meteorológicos"])


def settings(request):
    config = request.app.state.settings
    if not config.enable_article_simulations:
        raise HTTPException(404, "Ensaios meteorológicos não estão habilitados nesta API.")
    return config


@router.get("/status")
def status(request: Request):
    config = settings(request)
    return {"enabled": True, "purpose": "article-simulations", "environment": config.environment,
            "source_resolution_minutes": 60, "level_model": None}


@router.get("")
def catalogue(request: Request):
    return {"items": list_experiments(settings(request))}


@router.get("/{run_id}/export")
def export(run_id: str, request: Request):
    data = export_experiment(settings(request), run_id)
    return Response(data, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="floodsystem-ensaio-{run_id}.zip"',
        "Cache-Control": "no-store",
    })


@router.get("/{run_id}")
def detail(run_id: str, request: Request):
    return experiment_detail(settings(request), run_id)
