"""Download an immutable source snapshot. Never reads or writes a database."""

import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .model import generate, timestamp

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"


def read_snapshot(path):
    folder = Path(path)
    if folder.is_file():
        folder = folder.parent
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    raw = (folder / "response.json").read_bytes()
    return manifest, raw


def download(*, latitude, longitude, start_day, end_day, output):
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordenadas inválidas.")
    zone = ZoneInfo("America/Sao_Paulo")
    first, last = date.fromisoformat(start_day), date.fromisoformat(end_day)
    start = datetime.combine(first, time(), zone).astimezone(timezone.utc)
    end = datetime.combine(last + timedelta(days=1), time(), zone).astimezone(timezone.utc)
    if first > last or (last - first).days >= 31:
        raise ValueError("Informe de 1 a 31 dias; a data final é incluída.")
    params = {"latitude": latitude, "longitude": longitude, "start_date": start.date().isoformat(),
              "end_date": end.date().isoformat(), "hourly": "rain", "models": "era5",
              "timezone": "GMT", "timeformat": "unixtime", "precipitation_unit": "mm"}
    url = ENDPOINT + "?" + urlencode(params)
    with urlopen(Request(url, headers={"Accept": "application/json", "User-Agent": "FloodSystem-research/1"}), timeout=60) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError("Resposta excede o limite de 8 MB.")
    manifest = {"schema_version": 1, "provider": "open-meteo", "model": "era5", "variable": "rain",
                "request": {"endpoint": ENDPOINT, "parameters": params}, "request_url": url,
                "downloaded_at": timestamp(datetime.now(timezone.utc)), "start": timestamp(start), "end": timestamp(end),
                "display_timezone": "America/Sao_Paulo", "response_sha256": hashlib.sha256(raw).hexdigest(),
                "source_kind": "reanalysis", "source_resolution_minutes": 60,
                "citation": "Open-Meteo: doi:10.5281/zenodo.7970649; ERA5: doi:10.24381/cds.adbb2d47",
                "license": "Open-Meteo data: CC BY 4.0; preserve source attribution",
                "documentation_url": "https://open-meteo.com/en/docs/historical-weather-api",
                "importer_version": "open-meteo-snapshot-v1"}
    scenario = generate(manifest, raw)
    folder = Path(output) / scenario["dataset_id"]
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "response.json").write_bytes(raw)
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"snapshot": str(folder.resolve()), "source_total_mm": scenario["source_total_mm"],
            "expected_tip_count": scenario["expected_tip_count"], "notice": scenario["notice"]}
