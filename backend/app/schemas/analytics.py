"""Units, observation coverage and explicit unavailability for MVP calculations."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .telemetry import Identifier, IncomingInstant, InputModel, UTCInstant


class SummaryQuery(InputModel):
    device_id: Identifier
    start: IncomingInstant
    end: IncomingInstant
    window_minutes: float = Field(default=5.0, gt=0, le=1440, allow_inf_nan=False)

    @model_validator(mode="after")
    def chronological_period(self):
        if self.start >= self.end:
            raise ValueError("start precisa ser anterior a end.")
        return self


class Metric(BaseModel):
    value: float | None = Field(allow_inf_nan=False)
    unit: Literal["cm", "mm", "mm/h", "cm/min"]
    status: Literal["available", "unavailable"]
    reason: Literal[
        "numeric_overflow", "no_rain_events", "missing_k", "missing_h0",
        "ambiguous_endpoint", "insufficient_level_readings", "h0_changed",
        "nonpositive_elapsed_time", "period_shorter_than_window",
    ] | None


class RainCalibrationGroup(BaseModel):
    calibration_version: int | None
    k_mm_per_tip: float | None
    tip_count: int


class RainSummary(BaseModel):
    tip_count: int
    uncalibrated_tip_count: int
    calibrations: list[RainCalibrationGroup]
    accumulated_rainfall: Metric


class IntensitySummary(BaseModel):
    window_minutes: float
    start: UTCInstant
    end: UTCInstant
    rain: RainSummary | None
    intensity: Metric


class LevelEndpoint(BaseModel):
    reading_id: str | None
    measured_at: UTCInstant
    distance_cm: float | None
    calibration_version: int | None
    h0_cm: float | None
    level: Metric


class LevelSummary(BaseModel):
    reading_count: int
    uncalibrated_reading_count: int
    initial: LevelEndpoint | None
    final: LevelEndpoint | None
    elapsed_seconds: float | None
    level_change: Metric
    velocity: Metric


class PeriodSummary(BaseModel):
    device_id: str
    origin: Literal["simulation", "esp32"]
    start: UTCInstant
    end: UTCInstant
    rain: RainSummary
    intensity: IntensitySummary
    level: LevelSummary
