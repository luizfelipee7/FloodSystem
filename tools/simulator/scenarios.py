"""Deterministic example traces, not a hydrological model of the prototype."""

import hashlib
import json
from dataclasses import asdict
from datetime import timedelta

from .profile import SimulationProfile, parse_instant, timestamp

DEFAULT_STARTS = {
    "sem-chuva": "2026-10-08T12:00:00Z",
    "chuva-5min": "2026-10-08T13:00:00Z",
    "sobe-desce": "2026-10-08T14:00:00Z",
    "chuva-atraso": "2026-10-08T15:00:00Z",
}
GENERATOR_VERSION = 1


def build_scenario(name: str, start_text: str, profile: SimulationProfile, delay_seconds: int = 120) -> dict:
    start = parse_instant(start_text)
    if start < parse_instant(profile.valid_from):
        raise ValueError("O cenário precisa começar depois do início da calibração de simulação.")
    if type(delay_seconds) is not int or not 0 <= delay_seconds <= 3600:
        raise ValueError("O atraso deve estar entre 0 e 3600 segundos.")
    tips = []
    onset = None
    if name in ("sem-chuva", "chuva-5min"):
        points = [(second, 10.0) for second in (0, 60, 125, 190, 250, 299)]
        duration = 300
    elif name == "sobe-desce":
        points = list(zip((0, 47, 123, 205, 300, 376, 449, 527, 600),
                          (10.0, 11.0, 13.0, 16.0, 20.0, 18.0, 15.0, 12.0, 10.0)))
        duration = 601
    elif name == "chuva-atraso":
        # Delay is measured from the END of the five-minute rain window.
        onset = 300 + delay_seconds
        trace = {second: 10.0 for second in range(0, onset, 60)}
        trace.update({onset + index * 60: level for index, level in enumerate(
            (12.0, 14.0, 16.0, 18.0, 20.0, 18.0, 14.0, 10.0))})
        points = sorted(trace.items())
        duration = onset + 421
    else:
        raise ValueError("Cenário desconhecido.")
    if name in ("chuva-5min", "chuva-atraso"):
        tips = list(range(15, 300, 30))
    if profile.h0_cm < max(level for _, level in points):
        raise ValueError("O H0 simulado precisa acomodar todos os níveis do cenário (até 20 cm).")
    end = start + timedelta(seconds=duration)
    identity = {
        "generator_version": GENERATOR_VERSION, "scenario": name,
        "start": timestamp(start), "profile": asdict(profile),
        "delay_seconds": delay_seconds if name == "chuva-atraso" else None,
    }
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    readings = [
        {"device_id": profile.device_id, "reading_id": f"sim-{run_id}-level-{index:04d}",
         "measured_at": timestamp(start + timedelta(seconds=second)),
         "distance_cm": profile.h0_cm - level}
        for index, (second, level) in enumerate(points)
    ]
    events = [
        {"event_id": f"sim-{run_id}-tip-{index:04d}",
         "occurred_at": timestamp(start + timedelta(seconds=second))}
        for index, second in enumerate(tips)
    ]
    return {
        **identity, "run_id": run_id, "end": timestamp(end),
        "notice": "DADOS SINTÉTICOS. Não são medições ou resultados reais do protótipo.",
        "rain_window_end": timestamp(start + timedelta(minutes=5)) if tips else None,
        "first_level_change_at": timestamp(start + timedelta(seconds=onset)) if onset is not None else None,
        "level_readings": readings,
        "rain_batches": [{"device_id": profile.device_id, "events": events}] if events else [],
    }
