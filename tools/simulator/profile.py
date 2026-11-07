"""Explicit synthetic profile, also read by the backend's local setup command."""

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROFILE_PATH = Path(__file__).with_name("simulation-profile.json")


def parse_instant(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value):
        raise ValueError("Use ISO 8601 no horário de Brasília, por exemplo 2026-10-09T20:27:00-03:00.")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class SimulationProfile:
    profile_id: str
    simulation_only: bool
    device_id: str
    origin: str
    valid_from: str
    h0_cm: float
    k_mm_per_tip: float


def load_profile() -> SimulationProfile:
    data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != set(SimulationProfile.__dataclass_fields__):
        raise ValueError("Perfil de simulação inválido.")
    if data["simulation_only"] is not True or data["origin"] != "simulation" or data["device_id"] != "simulador-01":
        raise ValueError("Este perfil é exclusivo para simulador-01, com origem simulation.")
    if not isinstance(data["profile_id"], str) or not data["profile_id"].strip():
        raise ValueError("Informe profile_id.")
    for field in ("h0_cm", "k_mm_per_tip"):
        value = data[field]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 1e308:
            raise ValueError(f"{field} deve ser positivo e finito no perfil de simulação.")
        data[field] = float(value)
    data["valid_from"] = timestamp(parse_instant(data["valid_from"]))
    return SimulationProfile(**data)
