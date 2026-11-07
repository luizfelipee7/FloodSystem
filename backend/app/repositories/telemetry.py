"""Persist raw observations and calibration references; no HTTP or aggregates."""

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.config import Settings
from ..core.database import connection
from ..services.formulas import water_level


class DuplicateConflict(ValueError):
    """An identifier was reused with a different immutable payload."""


class DeviceNotFound(ValueError):
    """Observations require an explicitly registered device and origin."""


@dataclass(frozen=True)
class SaveResult:
    record: dict
    created: bool


def utc_timestamp(value: str | datetime) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("O horário precisa incluir fuso horário, por exemplo o sufixo Z para UTC.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def now_utc() -> str:
    return utc_timestamp(datetime.now(timezone.utc))


def identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} deve ser um texto não vazio, sem espaços nas extremidades.")
    return value


def measurement(value: float, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} deve ser numérico.")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{field} está fora do intervalo numérico.") from exc
    if not math.isfinite(number) or number >= 1e308 or number < 0 or (positive and number == 0):
        raise ValueError(f"{field} deve ser finito e {'positivo' if positive else 'não negativo'}.")
    return number


class TelemetryRepository:
    def __init__(self, settings: Settings):
        self.settings = settings

    def register_device(self, device_id: str, name: str, origin: str) -> SaveResult:
        if self.settings.enable_article_simulations:
            raise ValueError("Neste banco use exclusivamente prepare-weather-experiment.")
        identifier(device_id, "device_id")
        identifier(name, "name")
        if origin not in {"simulation", "esp32"}:
            raise ValueError("origin deve ser simulation ou esp32.")
        with connection(self.settings, write=True) as db:
            existing = db.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
            if existing:
                if existing["name"] != name or existing["origin"] != origin:
                    raise DuplicateConflict("O dispositivo já existe com outro nome ou origem.")
                return SaveResult(dict(existing), False)
            db.execute("INSERT INTO devices (device_id, name, origin, created_at) VALUES (?, ?, ?, ?)",
                       (device_id, name, origin, now_utc()))
            return SaveResult(dict(db.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()), True)

    def add_calibration(self, device_id: str, *, valid_from: str | datetime,
                        h0_cm: float | None = None, k_mm_per_tip: float | None = None) -> dict:
        if self.settings.enable_article_simulations:
            raise ValueError("Parâmetros dos ensaios são imutáveis. Prepare outra execução.")
        identifier(device_id, "device_id")
        start = utc_timestamp(valid_from)
        h0 = measurement(h0_cm, "h0_cm", positive=True) if h0_cm is not None else None
        k = measurement(k_mm_per_tip, "k_mm_per_tip", positive=True) if k_mm_per_tip is not None else None
        if h0 is None and k is None:
            raise ValueError("Informe pelo menos um parâmetro de calibração conhecido.")
        with connection(self.settings, write=True) as db:
            self._device(db, device_id)
            last = db.execute("SELECT * FROM calibrations WHERE device_id = ? ORDER BY version DESC LIMIT 1",
                              (device_id,)).fetchone()
            if last and start <= last["valid_from"]:
                raise ValueError("Uma nova versão precisa ter início posterior à versão anterior.")
            version = last["version"] + 1 if last else 1
            db.execute("INSERT INTO calibrations (device_id, version, valid_from, received_at, h0_cm, k_mm_per_tip) VALUES (?, ?, ?, ?, ?, ?)",
                       (device_id, version, start, now_utc(), h0, k))
            return dict(db.execute("SELECT * FROM calibrations WHERE device_id = ? AND version = ?",
                                   (device_id, version)).fetchone())

    @staticmethod
    def _device(db, device_id):
        row = db.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
        if row is None:
            raise DeviceNotFound("Dispositivo não cadastrado.")
        return row

    @staticmethod
    def _calibration(db, device_id, timestamp):
        return db.execute("SELECT * FROM calibrations WHERE device_id = ? AND valid_from <= ? ORDER BY valid_from DESC LIMIT 1",
                          (device_id, timestamp)).fetchone()

    def save_level_reading(self, device_id: str, reading_id: str, *, measured_at: str | datetime,
                          distance_cm: float) -> SaveResult:
        if self.settings.enable_article_simulations:
            raise ValueError("Esta etapa dos ensaios gera somente chuva; o modelo de nível ainda não está habilitado.")
        identifier(device_id, "device_id")
        identifier(reading_id, "reading_id")
        timestamp = utc_timestamp(measured_at)
        distance = measurement(distance_cm, "distance_cm")
        with connection(self.settings, write=True) as db:
            device = self._device(db, device_id)
            existing = db.execute("SELECT * FROM level_readings WHERE device_id = ? AND reading_id = ?",
                                  (device_id, reading_id)).fetchone()
            if existing:
                if existing["measured_at"] != timestamp or existing["distance_cm"] != distance:
                    raise DuplicateConflict("reading_id já utilizado com outra leitura.")
                return SaveResult(dict(existing), False)
            calibration = self._calibration(db, device_id, timestamp)
            version = calibration["version"] if calibration else None
            level = water_level(distance, calibration["h0_cm"] if calibration else None)
            db.execute("INSERT INTO level_readings (device_id, reading_id, measured_at, received_at, distance_cm, water_level_cm, origin, calibration_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (device_id, reading_id, timestamp, now_utc(), distance, level, device["origin"], version))
            return SaveResult(dict(db.execute("SELECT * FROM level_readings WHERE device_id = ? AND reading_id = ?",
                                             (device_id, reading_id)).fetchone()), True)

    def save_rain_tip(self, device_id: str, event_id: str, *, occurred_at: str | datetime) -> SaveResult:
        return self.save_rain_tips(device_id, [(event_id, occurred_at)])[0]

    def save_rain_tips(self, device_id: str, events: list[tuple[str, str | datetime]]) -> list[SaveResult]:
        """Accept the entire batch in one transaction, or roll it all back."""
        identifier(device_id, "device_id")
        if not events:
            raise ValueError("O lote precisa conter pelo menos um evento.")
        normalized = [(identifier(event_id, "event_id"), utc_timestamp(timestamp)) for event_id, timestamp in events]
        with connection(self.settings, write=True) as db:
            device = self._device(db, device_id)
            run = None
            if self.settings.enable_article_simulations:
                run = db.execute("SELECT run_id FROM simulation_runs WHERE device_id = ?", (device_id,)).fetchone()
                if run is None or device["origin"] != "simulation":
                    raise ValueError("Dispositivo sem ensaio meteorológico preparado.")
            results = []
            for event_id, timestamp in normalized:
                if run is not None:
                    expected = db.execute("SELECT occurred_at FROM simulation_expected_tips WHERE run_id = ? AND event_id = ?",
                                          (run["run_id"], event_id)).fetchone()
                    if expected is None or expected["occurred_at"] != timestamp:
                        raise DuplicateConflict("Evento não corresponde ao manifesto imutável deste ensaio.")
                existing = db.execute("SELECT * FROM rain_tip_events WHERE device_id = ? AND event_id = ?",
                                      (device_id, event_id)).fetchone()
                if existing:
                    if existing["occurred_at"] != timestamp:
                        raise DuplicateConflict("event_id já utilizado com outro horário; o lote não foi gravado.")
                    results.append(SaveResult(dict(existing), False))
                    continue
                calibration = self._calibration(db, device_id, timestamp)
                version = calibration["version"] if calibration else None
                db.execute("INSERT INTO rain_tip_events (device_id, event_id, occurred_at, received_at, origin, calibration_version) VALUES (?, ?, ?, ?, ?, ?)",
                           (device_id, event_id, timestamp, now_utc(), device["origin"], version))
                record = db.execute("SELECT * FROM rain_tip_events WHERE device_id = ? AND event_id = ?",
                                    (device_id, event_id)).fetchone()
                results.append(SaveResult(dict(record), True))
            return results

    def list_level_readings(self, device_id: str, *, start=None, end=None, limit: int = 100, offset: int = 0) -> list[dict]:
        return self._list_observations("level", device_id, start, end, limit, offset)

    def list_rain_tips(self, device_id: str, *, start=None, end=None, limit: int = 100, offset: int = 0) -> list[dict]:
        return self._list_observations("rain", device_id, start, end, limit, offset)

    def latest_rain_tip(self, device_id: str) -> dict | None:
        identifier(device_id, "device_id")
        with connection(self.settings) as db:
            self._device(db, device_id)
            row = db.execute(
                "SELECT * FROM rain_tip_events WHERE device_id = ? ORDER BY rowid DESC LIMIT 1",
                (device_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def latest_level_reading(self, device_id: str) -> dict | None:
        identifier(device_id, "device_id")
        with connection(self.settings) as db:
            self._device(db, device_id)
            row = db.execute(
                "SELECT * FROM level_readings WHERE device_id = ? ORDER BY rowid DESC LIMIT 1",
                (device_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def _list_observations(self, kind, device_id, start, end, limit, offset):
        identifier(device_id, "device_id")
        if type(limit) is not int or not 1 <= limit <= 1001 or type(offset) is not int or offset < 0:
            raise ValueError("Paginação inválida.")
        if (start is None) != (end is None):
            raise ValueError("Informe início e fim do período juntos.")
        # Identifiers are a fixed allowlist; external values always use SQL parameters.
        table, time_column, id_column = {
            "level": ("level_readings", "measured_at", "reading_id"),
            "rain": ("rain_tip_events", "occurred_at", "event_id"),
        }[kind]
        query = f"SELECT * FROM {table} WHERE device_id = ?"
        parameters = [device_id]
        if start is not None:
            start, end = utc_timestamp(start), utc_timestamp(end)
            if start >= end:
                raise ValueError("O início precisa ser anterior ao fim do período.")
            query += f" AND {time_column} >= ? AND {time_column} < ?"
            parameters.extend((start, end))
        query += f" ORDER BY {time_column}, {id_column} LIMIT ? OFFSET ?"
        parameters.extend((limit, offset))
        with connection(self.settings) as db:
            self._device(db, device_id)
            return [dict(row) for row in db.execute(query, parameters)]
