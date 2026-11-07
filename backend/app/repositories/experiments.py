"""Explicit preparation, provenance and complete exports of isolated rainfall runs."""

import csv
import io
import json
import sqlite3
import zipfile
from decimal import Decimal

from ..core.config import resolve_path
from ..core.database import connection, initialize_database
from .telemetry import DeviceNotFound, DuplicateConflict, now_utc
from tools.weather_simulator.model import H0, K, NOTICE, canonical, generate, text_decimal


def require_experiments(settings):
    if (not settings.enable_article_simulations or settings.environment == "production"
            or settings.database_path in {resolve_path("database/development.db"), resolve_path("database/production.db")}):
        raise ValueError("Use a API dos ensaios, com banco exclusivo e FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS=true.")


def check_experiment_database(settings):
    """Inspect an existing file read-only, before initialization/migrations."""
    require_experiments(settings)
    if settings.database_path.exists():
        with sqlite3.connect(settings.database_path.as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='devices'").fetchone():
                if db.execute("SELECT 1 FROM devices WHERE origin != 'simulation' OR device_id NOT LIKE 'sim-artigo-%' LIMIT 1").fetchone():
                    raise ValueError("O banco selecionado contém dispositivos externos aos ensaios meteorológicos.")


def prepare_experiment(settings, manifest, raw, initial_residual="0"):
    check_experiment_database(settings)
    scenario = generate(manifest, raw, initial_residual)
    initialize_database(settings)
    with connection(settings, write=True) as db:
        if db.execute("SELECT 1 FROM devices WHERE origin != 'simulation' OR device_id NOT LIKE 'sim-artigo-%' LIMIT 1").fetchone():
            raise ValueError("Este banco contém dispositivos externos aos ensaios do artigo. Escolha outro arquivo.")
        existing = db.execute("SELECT * FROM simulation_runs WHERE run_id = ?", (scenario["run_id"],)).fetchone()
        if existing:
            return {"created": False, "run_id": scenario["run_id"], "device_id": scenario["device_id"],
                    "expected_tip_count": scenario["expected_tip_count"], "database": str(settings.database_path)}
        dataset_id, run_id, device_id = (scenario[key] for key in ("dataset_id", "run_id", "device_id"))
        source = db.execute("SELECT 1 FROM weather_datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
        if not source:
            db.execute("INSERT INTO weather_datasets VALUES (?, ?, ?, ?, ?)",
                       (dataset_id, canonical(manifest), raw, manifest["response_sha256"], now_utc()))
            db.executemany("INSERT INTO weather_intervals VALUES (?, ?, ?, ?, ?, ?)", [
                (dataset_id, row["index"], row["start"], row["end"], row["source_time"], row["rain_mm"])
                for row in scenario["intervals"]])
        if db.execute("SELECT 1 FROM devices WHERE device_id = ?", (device_id,)).fetchone():
            raise DuplicateConflict("Identificador do ensaio já ocupado. Nenhum cadastro foi substituído.")
        db.execute("INSERT INTO devices VALUES (?, ?, 'simulation', ?)",
                   (device_id, f"Ensaio Open-Meteo ERA5 {run_id}", now_utc()))
        db.execute("INSERT INTO calibrations VALUES (?, 1, ?, ?, ?, ?)",
                   (device_id, scenario["start"], now_utc(), float(H0), float(K)))
        db.execute("INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (run_id, dataset_id, device_id, scenario["start"], scenario["end"], canonical(scenario["profile"]),
                    canonical(scenario["grid"]), scenario["source_total_mm"], scenario["final_residual_mm"],
                    scenario["expected_tip_count"], scenario["expected_rain_mm"], now_utc()))
        db.executemany("INSERT INTO simulation_steps VALUES (?, ?, ?, ?, ?, ?, ?)", [
            (run_id, row["index"], row["residual_before_mm"], row["residual_after_mm"], row["expected_tip_count"],
             row["expected_rain_mm"], row["cumulative_source_mm"]) for row in scenario["intervals"]])
        db.executemany("INSERT INTO simulation_expected_tips VALUES (?, ?, ?, ?)", [
            (run_id, event["interval_index"], event["event_id"], event["occurred_at"]) for event in scenario["events"]])
    return {"created": True, "run_id": run_id, "device_id": device_id,
            "expected_tip_count": scenario["expected_tip_count"], "database": str(settings.database_path)}


def _detail(db, run_id):
    row = db.execute("SELECT * FROM simulation_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise DeviceNotFound("Ensaio não encontrado nesta API.")
    result = dict(row)
    result["profile"] = json.loads(result.pop("profile_json"))
    result["grid"] = json.loads(result.pop("grid_json"))
    source = db.execute("SELECT manifest_json, imported_at FROM weather_datasets WHERE dataset_id = ?",
                        (row["dataset_id"],)).fetchone()
    result["source"] = json.loads(source["manifest_json"])
    result["imported_at"] = source["imported_at"]
    result["notice"] = NOTICE
    result["origin"] = "simulation"
    counts = {r["interval_index"]: r["n"] for r in db.execute("""
        SELECT e.interval_index, COUNT(*) AS n FROM simulation_expected_tips e
        JOIN rain_tip_events t ON t.device_id = ? AND t.event_id = e.event_id
            AND t.occurred_at = e.occurred_at AND t.calibration_version = 1 AND t.origin = 'simulation'
        WHERE e.run_id = ? GROUP BY e.interval_index
    """, (row["device_id"], run_id))}
    result["received_tip_count"] = sum(counts.values())
    result["status"] = "complete" if result["received_tip_count"] == row["expected_tip_count"] else "pending"
    k = Decimal(result["profile"]["k_mm_per_tip"])
    result["received_rain_mm"] = text_decimal(result["received_tip_count"] * k)
    intervals = []
    for step in db.execute("""
        SELECT w.*, s.residual_before_mm, s.residual_after_mm, s.expected_tip_count,
               s.expected_rain_mm, s.cumulative_source_mm
        FROM simulation_steps s JOIN weather_intervals w
          ON w.dataset_id = ? AND w.interval_index = s.interval_index
        WHERE s.run_id = ? ORDER BY s.interval_index
    """, (row["dataset_id"], run_id)):
        item = dict(step)
        item["received_tip_count"] = counts.get(item["interval_index"], 0)
        item["received_rain_mm"] = text_decimal(item["received_tip_count"] * k)
        # Exactly one hour: amount in mm numerically equals hourly mean in mm/h.
        item["source_intensity_mm_h"] = item["rain_mm"]
        item["tip_intensity_mm_h"] = item["received_rain_mm"] if result["status"] == "complete" else None
        intervals.append(item)
    result["intervals"] = intervals
    return result


def experiment_detail(settings, run_id):
    require_experiments(settings)
    with connection(settings) as db:
        db.execute("BEGIN")
        return _detail(db, run_id)


def list_experiments(settings):
    require_experiments(settings)
    with connection(settings) as db:
        return [dict(row) for row in db.execute("""
            SELECT run_id, device_id, start_at, end_at, source_total_mm, expected_tip_count, created_at
            FROM simulation_runs ORDER BY created_at DESC
        """)]


def _csv(rows, columns):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(columns)
    for row in rows:
        values = []
        for key in columns:
            value = row.get(key, "")
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return output.getvalue().encode("utf-8-sig")


def export_experiment(settings, run_id):
    require_experiments(settings)
    with connection(settings) as db:
        db.execute("BEGIN")
        detail = _detail(db, run_id)
        if detail["status"] != "complete":
            raise DuplicateConflict("Envio incompleto. Retome o mesmo cenário antes de exportar resultados.")
        source = db.execute("SELECT raw_response, manifest_json FROM weather_datasets WHERE dataset_id = ?",
                            (detail["dataset_id"],)).fetchone()
        events = [dict(r) for r in db.execute("""
            SELECT t.*, e.interval_index FROM rain_tip_events t JOIN simulation_expected_tips e
              ON e.run_id = ? AND e.event_id = t.event_id
            WHERE t.device_id = ? ORDER BY t.occurred_at, t.event_id
        """, (run_id, detail["device_id"]))]
        for event in events:
            event.update(run_id=run_id, dataset_id=detail["dataset_id"], k_mm_per_tip=K)
        raw = bytes(source["raw_response"])
        source_manifest = source["manifest_json"]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source-response.json", raw)
        archive.writestr("source-manifest.json", source_manifest)
        archive.writestr("experiment.json", json.dumps(detail, ensure_ascii=False, indent=2))
        archive.writestr("hourly-comparison.csv", _csv(detail["intervals"], [
            "dataset_id", "interval_index", "start_at", "end_at", "source_time", "rain_mm",
            "source_intensity_mm_h", "expected_tip_count", "received_tip_count", "received_rain_mm",
            "tip_intensity_mm_h", "residual_before_mm", "residual_after_mm", "cumulative_source_mm"]))
        archive.writestr("simulated-events.csv", _csv(events, [
            "run_id", "dataset_id", "device_id", "event_id", "interval_index", "occurred_at",
            "received_at", "origin", "calibration_version", "k_mm_per_tip"]))
        archive.writestr("README.txt", (NOTICE + "\n"
            "Fonte: Open-Meteo / ERA5. Dados horários de reanálise; variável rain.\n"
            "Distribuição uniforme por hora; basculadas simuladas com residual contínuo.\n"
            "Horários UTC; comparação em 60 minutos. Intensidade sub-horária não foi observada.\n"
            "Cruzamentos no fim da hora são representados 1 microssegundo antes, mantendo [start,end).\n"
            "H0=23 cm está registrado; este ensaio não gera nível de água.\n"
            "Zeros na comparação são contagens de uma execução completa, não comprovação de cobertura de sensor físico.\n"
            "CSVs completos; parâmetros e proveniência em experiment.json.\n"))
    return output.getvalue()
