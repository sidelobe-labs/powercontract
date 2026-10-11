from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["PASS", "FAIL"]
Direction = Literal["above", "below"]


@dataclass(frozen=True)
class SignalSpec:
    name: str
    column: str
    nominal: float | None = None


@dataclass(frozen=True)
class EventSpec:
    name: str
    signal: str
    direction: Direction
    threshold: float
    stable_for: float = 0.0


@dataclass(frozen=True)
class RequirementSpec:
    id: str
    type: str
    raw: dict[str, object]


@dataclass(frozen=True)
class Contract:
    time_column: str
    signals: dict[str, SignalSpec]
    events: dict[str, EventSpec]
    requirements: tuple[RequirementSpec, ...]


@dataclass(frozen=True)
class Capture:
    time: tuple[float, ...]
    signals: dict[str, tuple[float, ...]]


@dataclass(frozen=True)
class Finding:
    requirement_id: str
    status: Status
    summary: str
    measured: float | None = None
    limit: float | None = None
    margin: float | None = None
    unit: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.requirement_id,
            "status": self.status,
            "summary": self.summary,
            "measured": self.measured,
            "limit": self.limit,
            "margin": self.margin,
            "unit": self.unit,
        }
