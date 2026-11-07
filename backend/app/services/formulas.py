"""Elementary conversions shared by ingestion and period summaries."""


def water_level(distance_cm: float, h0_cm: float | None) -> float | None:
    return None if h0_cm is None else h0_cm - distance_cm
