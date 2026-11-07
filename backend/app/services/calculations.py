"""MVP formulas. Missing calibration is never replaced by a physical guess."""

import math
from datetime import datetime, timedelta

from ..repositories.analytics import AnalyticsRepository
from ..repositories.telemetry import utc_timestamp
from .formulas import water_level


def metric(value, unit, reason=None):
    if value is not None and not math.isfinite(value):
        value, reason = None, "numeric_overflow"
    return {
        "value": value, "unit": unit,
        "status": "available" if value is not None else "unavailable",
        "reason": reason,
    }


def rainfall(groups):
    count = sum(group["tip_count"] for group in groups)
    missing = sum(group["tip_count"] for group in groups if group["k_mm_per_tip"] is None)
    if not count:
        value = metric(None, "mm", "no_rain_events")
    elif missing:
        value = metric(None, "mm", "missing_k")
    else:
        try:
            total = math.fsum(group["tip_count"] * group["k_mm_per_tip"] for group in groups)
        except OverflowError:
            total = math.inf
        value = metric(total, "mm")
    return {
        "tip_count": count, "uncalibrated_tip_count": missing,
        "calibrations": groups, "accumulated_rainfall": value,
    }


def endpoint(row):
    if row is None:
        return None
    # Conflicting observations at the same instant do not define an endpoint.
    level = water_level(row["distance_cm"], row["h0_cm"])
    reason = "ambiguous_endpoint" if row["ambiguous"] else "missing_h0" if level is None else None
    return {
        "reading_id": None if row["ambiguous"] else row["reading_id"],
        "measured_at": row["measured_at"],
        "distance_cm": None if row["ambiguous"] else row["distance_cm"],
        "calibration_version": None if row["ambiguous"] else row["calibration_version"],
        "h0_cm": None if row["ambiguous"] else row["h0_cm"],
        "level": metric(None if reason else level, "cm", reason),
    }


def level_summary(rows):
    first, last = endpoint(rows["initial"]), endpoint(rows["final"])
    elapsed = None
    if first is not None and last is not None:
        elapsed = (datetime.fromisoformat(last["measured_at"]) -
                   datetime.fromisoformat(first["measured_at"])).total_seconds()
    if rows["reading_count"] < 2:
        reason = "insufficient_level_readings"
    elif first["level"]["reason"] == "ambiguous_endpoint" or last["level"]["reason"] == "ambiguous_endpoint":
        reason = "ambiguous_endpoint"
    elif rows["uncalibrated_count"]:
        reason = "missing_h0"
    elif rows["h0_count"] > 1:
        reason = "h0_changed"
    elif elapsed <= 0:
        reason = "nonpositive_elapsed_time"
    else:
        reason = None
    delta = metric(None, "cm", reason) if reason else metric(
        last["level"]["value"] - first["level"]["value"], "cm")
    velocity = metric(None, "cm/min", delta["reason"]) if delta["value"] is None else metric(
        delta["value"] / elapsed * 60, "cm/min")
    return {
        "reading_count": rows["reading_count"], "uncalibrated_reading_count": rows["uncalibrated_count"],
        "initial": first, "final": last, "elapsed_seconds": elapsed,
        "level_change": delta, "velocity": velocity,
    }


def period_summary(settings, *, device_id, start, end, window_minutes=5.0):
    start = datetime.fromisoformat(utc_timestamp(start))
    end = datetime.fromisoformat(utc_timestamp(end))
    if start >= end:
        raise ValueError("start precisa ser anterior a end.")
    if isinstance(window_minutes, bool) or not isinstance(window_minutes, (int, float)) or not 0 < window_minutes <= 1440:
        raise ValueError("window_minutes precisa ser maior que zero e no máximo 1440.")
    window = timedelta(minutes=window_minutes)
    if window.total_seconds() <= 0:
        raise ValueError("A janela precisa ter duração de pelo menos um microssegundo.")
    try:
        window_start = end - window
    except OverflowError as exc:
        raise ValueError("A janela ultrapassa o intervalo de datas permitido.") from exc
    snapshot = AnalyticsRepository(settings).summary_snapshot(
        device_id, start=start, end=end, window_start=window_start)
    rain = rainfall(snapshot["rain"])
    window_rain = snapshot["window_rain"]
    if window_rain is None:
        intensity = metric(None, "mm/h", "period_shorter_than_window")
        window_result = None
    else:
        window_result = rainfall(window_rain)
        amount = window_result["accumulated_rainfall"]
        intensity = metric(None, "mm/h", amount["reason"]) if amount["value"] is None else metric(
            amount["value"] / window.total_seconds() * 3600, "mm/h")
    return {
        "device_id": device_id, "origin": snapshot["origin"], "start": start, "end": end,
        "rain": rain,
        "intensity": {
            "window_minutes": window.total_seconds() / 60, "start": window_start, "end": end,
            "rain": window_result, "intensity": intensity,
        },
        "level": level_summary(snapshot["levels"]),
    }
