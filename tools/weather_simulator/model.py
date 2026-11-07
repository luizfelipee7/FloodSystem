"""Pure, deterministic conversion. No network, SQLite or physical telemetry."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

VERSION = "hourly-rain-v1"
H0 = "23"
K = "2.17"
SOURCE_URL = "https://open-meteo.com/en/docs/historical-weather-api"
NOTICE = "Ensaio simulado com chuva horária de reanálise. Não representa medição de campo do protótipo."


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def instant(value):
    if not isinstance(value, str):
        raise ValueError("Informe horário ISO 8601 com fuso.")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("Horário sem fuso não é aceito.")
    return result.astimezone(timezone.utc)


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def decimal(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Chuva ausente ou inválida; não é convertida em zero.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Valor decimal inválido.") from exc
    if not number.is_finite() or not 0 <= number <= 1000000:
        raise ValueError("O valor deve ser finito, não negativo e de até 1.000.000 mm.")
    return number


def text_decimal(value):
    return format(value.normalize(), "f")


def normalize(manifest, raw):
    """Provider label t is the sum over the preceding hour, stored as [t-1h,t)."""
    if manifest.get("schema_version") != 1 or manifest.get("provider") != "open-meteo":
        raise ValueError("Manifesto de fonte não reconhecido.")
    params = manifest.get("request", {}).get("parameters", {})
    if (manifest["request"].get("endpoint") != "https://archive-api.open-meteo.com/v1/archive"
            or params.get("models") != "era5" or params.get("hourly") != "rain"
            or params.get("timezone") != "GMT" or params.get("timeformat") != "unixtime"
            or params.get("precipitation_unit") != "mm"):
        raise ValueError("A primeira versão exige ERA5, rain, mm e timestamps Unix em GMT.")
    if hashlib.sha256(raw).hexdigest() != manifest.get("response_sha256"):
        raise ValueError("A resposta original difere do hash do manifesto.")
    payload = json.loads(raw, parse_float=Decimal)
    if payload.get("error") or payload.get("utc_offset_seconds") != 0:
        raise ValueError("Resposta meteorológica inválida ou fora de UTC.")
    if payload.get("hourly_units", {}).get("rain") != "mm":
        raise ValueError("Unidade de chuva inesperada.")
    hourly = payload.get("hourly", {})
    times, amounts = hourly.get("time", []), hourly.get("rain", [])
    if not times or len(times) != len(amounts):
        raise ValueError("Série horária incompleta.")
    start, end = instant(manifest["start"]), instant(manifest["end"])
    if start >= end or (end - start).total_seconds() > 31 * 86400:
        raise ValueError("Selecione um período entre uma hora e 31 dias.")
    if any(t.minute or t.second or t.microsecond for t in (start, end)):
        raise ValueError("O recorte deve ser alinhado a horas UTC inteiras.")
    by_end = {}
    for label, amount in zip(times, amounts):
        if isinstance(label, bool) or not isinstance(label, int):
            raise ValueError("Timestamp da fonte inválido.")
        at = datetime.fromtimestamp(label, timezone.utc)
        if at in by_end:
            raise ValueError("Horário duplicado na fonte.")
        by_end[at] = amount
    intervals = []
    cursor = start
    while cursor < end:
        finish = cursor + timedelta(hours=1)
        if finish not in by_end:
            raise ValueError(f"Falta a hora encerrada em {timestamp(finish)}.")
        amount = decimal(by_end[finish])
        intervals.append({"index": len(intervals), "start": timestamp(cursor),
                          "end": timestamp(finish), "source_time": timestamp(finish),
                          "rain_mm": text_decimal(amount)})
        cursor = finish
    metadata = {key: str(payload.get(key)) for key in ("latitude", "longitude", "elevation")}
    return intervals, metadata


def generate(manifest, raw, initial_residual="0"):
    intervals, grid = normalize(manifest, raw)
    k = Decimal(K)
    residual = decimal(initial_residual)
    if residual >= k:
        raise ValueError("Residual inicial deve ser menor que K.")
    dataset_identity = {"response_sha256": manifest["response_sha256"],
                        "request": manifest["request"], "start": manifest["start"], "end": manifest["end"]}
    dataset_id = digest(dataset_identity)
    profile = {"generator_version": VERSION, "dataset_id": dataset_id, "h0_cm": H0,
               "k_mm_per_tip": K, "initial_residual_mm": text_decimal(residual),
               "distribution": "uniform_within_each_hour", "level_model": None,
               "timestamp_rule": "threshold rounded to microsecond; hour end uses preceding microsecond",
               "source_interval_rule": "preceding hour sum normalized as [start,end)",
               "analysis_window_minutes": 60}
    run_id = digest(profile)[:24]
    device_id = f"sim-artigo-{run_id}"
    events, steps = [], []
    source_total = Decimal(0)
    for interval in intervals:
        amount = Decimal(interval["rain_mm"])
        before = residual
        count = int((before + amount) // k)
        if len(events) + count > 100000:
            raise ValueError("Ensaio excede o limite de 100.000 eventos; reduza o período.")
        start = instant(interval["start"])
        for index in range(count):
            fraction = (k * (index + 1) - before) / amount
            offset = int((fraction * Decimal(3600000000)).to_integral_value(rounding=ROUND_HALF_EVEN))
            # A crossing at the hour boundary is represented by its left limit.
            # Maximum timestamp displacement: 1 microsecond, explicitly in the profile.
            offset = max(0, min(offset, 3599999999))
            events.append({"event_id": f"met-{run_id}-{len(events):07d}",
                           "occurred_at": timestamp(start + timedelta(microseconds=offset)),
                           "interval_index": interval["index"]})
        residual = before + amount - count * k
        source_total += amount
        steps.append({**interval, "residual_before_mm": text_decimal(before),
                      "residual_after_mm": text_decimal(residual), "expected_tip_count": count,
                      "expected_rain_mm": text_decimal(count * k),
                      "cumulative_source_mm": text_decimal(source_total)})
    return {"run_id": run_id, "dataset_id": dataset_id, "device_id": device_id,
            "start": timestamp(instant(manifest["start"])), "end": timestamp(instant(manifest["end"])),
            "profile": profile, "grid": grid, "notice": NOTICE, "intervals": steps, "events": events,
            "source_total_mm": text_decimal(source_total), "final_residual_mm": text_decimal(residual),
            "expected_tip_count": len(events), "expected_rain_mm": text_decimal(len(events) * k)}
