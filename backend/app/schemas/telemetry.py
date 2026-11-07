"""Version 1 contracts for raw telemetry and period queries."""

import re
from datetime import timezone
from typing import Annotated, Literal

from pydantic import (
    AfterValidator, AwareDatetime, BaseModel, BeforeValidator, ConfigDict,
    Field, PlainSerializer, StringConstraints, model_validator,
)

from ..repositories.telemetry import identifier, utc_timestamp


def timestamp_text(value):
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("Use data/hora ISO 8601 com segundos e fuso, por exemplo 2026-10-06T14:05:00Z.")
    return value


Identifier = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=128),
    AfterValidator(lambda value: identifier(value, "identificador")),
]
UTCInstant = Annotated[
    AwareDatetime,
    AfterValidator(lambda value: value.astimezone(timezone.utc)),
    PlainSerializer(utc_timestamp, return_type=str, when_used="json"),
]
IncomingInstant = Annotated[UTCInstant, BeforeValidator(timestamp_text)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LevelReadingInput(InputModel):
    device_id: Identifier
    reading_id: Identifier
    measured_at: IncomingInstant
    distance_cm: Annotated[float, Field(strict=True, ge=0, lt=1e308, allow_inf_nan=False)]


class RainTipInput(InputModel):
    event_id: Identifier
    occurred_at: IncomingInstant


class RainBatchInput(InputModel):
    device_id: Identifier
    events: Annotated[list[RainTipInput], Field(min_length=1, max_length=500)]


class PeriodQuery(InputModel):
    device_id: Identifier
    start: IncomingInstant
    end: IncomingInstant
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def chronological_period(self):
        if self.start >= self.end:
            raise ValueError("start precisa ser anterior a end.")
        return self


class StoredObservation(BaseModel):
    device_id: str
    received_at: UTCInstant
    origin: Literal["simulation", "esp32"]
    calibration_version: int | None


class LevelReading(StoredObservation):
    reading_id: str
    measured_at: UTCInstant
    distance_cm: float
    water_level_cm: float | None


class RainTip(StoredObservation):
    event_id: str
    occurred_at: UTCInstant


class LevelWriteResult(BaseModel):
    created: bool
    reading: LevelReading


class RainWriteResult(BaseModel):
    created: bool
    event: RainTip


class RainBatchResult(BaseModel):
    inserted_count: int
    duplicate_count: int
    results: list[RainWriteResult]


class Page(BaseModel):
    device_id: str
    start: UTCInstant
    end: UTCInstant
    limit: int
    offset: int
    has_more: bool


class LevelPage(Page):
    items: list[LevelReading]


class RainPage(Page):
    items: list[RainTip]
