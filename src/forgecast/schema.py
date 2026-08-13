from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DisruptionType(str, Enum):
    EXPORT_RESTRICTION = "export_restriction"
    PORT_BORDER_CLOSURE = "port_border_closure"
    SANCTIONS = "sanctions"
    CIVIL_UNREST = "civil_unrest"
    CONFLICT_ESCALATION = "conflict_escalation"
    FACTORY_SHUTDOWN = "factory_shutdown"
    SHIPPING_THREAT = "shipping_threat"
    ASSET_SEIZURE = "asset_seizure"


class Event(BaseModel):
    id: str
    timestamp: datetime
    actor: str
    actor_country: str
    action: str
    action_code: str
    target: str | None = None
    target_country: str | None = None
    material: str | None = None
    location: str | None = None
    goldstein: float = 0.0
    tone: float = 0.0
    source_url: str | None = None
    source: str = "sample"
    disruption_type: DisruptionType | None = None


class Relation(BaseModel):
    timestamp: datetime
    subject: str
    predicate: str
    object: str
    material: str | None = None
    confidence: float = 1.0
    event_id: str | None = None


class Outcome(BaseModel):
    occurred_on: date
    country: str
    material: str | None = None
    disruption_type: DisruptionType
    name: str
    notes: str = ""


class Driver(BaseModel):
    indicator: str
    direction: Literal["up", "down"]
    detail: str


class AnalogMatch(BaseModel):
    name: str
    similarity: float
    year: int
    country: str
    material: str | None = None
    outcome: str
    difference: str


class ForecastItem(BaseModel):
    id: str = ""
    disruption_type: DisruptionType
    actor_country: str
    actor_name: str
    material: str | None = None
    chokepoint: str | None = None
    site: str | None = None
    lat: float | None = None
    lon: float | None = None
    probability: float = Field(ge=0, le=1)
    previous_probability: float | None = None
    delta: float | None = None
    drivers: list[Driver] = Field(default_factory=list)
    analogs: list[AnalogMatch] = Field(default_factory=list)
    would_increase: list[str] = Field(default_factory=list)
    would_decrease: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    exposed_programs: list[str] = Field(default_factory=list)
    exposed_suppliers: list[str] = Field(default_factory=list)


class ForecastReport(BaseModel):
    as_of: date
    horizon_days: int
    portfolio: str
    items: list[ForecastItem]
    notes: list[str] = Field(default_factory=list)


class MapPin(BaseModel):
    id: str
    lat: float
    lon: float
    kind: Literal["forecast", "supplier"]
    label: str
    subtitle: str = ""
    site: str | None = None
    country: str
    material: str | None = None
    disruption_type: DisruptionType | None = None
    probability: float | None = None
    previous_probability: float | None = None
    delta: float | None = None
    chokepoint: str | None = None
    rank: int = 0
    exposed_programs: list[str] = Field(default_factory=list)
    exposed_suppliers: list[str] = Field(default_factory=list)
    drivers: list[Driver] = Field(default_factory=list)
    analogs: list[AnalogMatch] = Field(default_factory=list)
    would_increase: list[str] = Field(default_factory=list)
    would_decrease: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    headline: str = ""


class PulseEvent(BaseModel):
    id: str
    lat: float
    lon: float
    timestamp: datetime
    actor_country: str
    actor_name: str
    action: str
    material: str | None = None
    tone: float = 0.0
    location: str | None = None


class MapPayload(BaseModel):
    as_of: date
    horizon_days: int
    portfolio: str
    programs: list[str] = Field(default_factory=list)
    pins: list[MapPin]
    suppliers: list[MapPin] = Field(default_factory=list)
    pulse: list[PulseEvent] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DemoBundle(BaseModel):
    default_as_of: date
    horizon_days: int
    dates: list[date]
    snapshots: dict[str, MapPayload]


class BacktestScores(BaseModel):
    n: int
    brier: float
    log_loss: float
    base_rate: float
    baseline_brier: float
    brier_skill: float
    reliability: list[dict] = Field(default_factory=list)
