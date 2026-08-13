from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    LOAD_GROWTH = "load_growth"
    PERMIT_MW = "permit_mw"
    GIGA_SITE = "giga_site"


@dataclass(frozen=True)
class Entity:
    geo_id: str
    geo_kind: Literal["ba", "county"]
    signal: SignalType


class Event(BaseModel):
    id: str
    timestamp: datetime
    actor: str
    actor_country: str = "US"
    action: str
    action_code: str
    target: str | None = None
    target_country: str | None = None
    theme: str | None = None
    location: str | None = None
    lat: float | None = None
    lon: float | None = None
    h3: str | None = None
    geo_id: str | None = None
    geo_kind: Literal["ba", "county", "site"] | None = None
    goldstein: float = 0.0
    tone: float = 0.0
    source_url: str | None = None
    source: str = "sample"
    signal_type: SignalType | None = None


class Relation(BaseModel):
    timestamp: datetime
    subject: str
    predicate: str
    object: str
    theme: str | None = None
    confidence: float = 1.0
    event_id: str | None = None


class Outcome(BaseModel):
    occurred_on: date
    geo_id: str
    geo_kind: Literal["ba", "county"]
    signal_type: SignalType
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
    geo_id: str
    geo_name: str = ""
    signal_type: SignalType | None = None
    outcome: str
    difference: str


class TickerHit(BaseModel):
    ticker: str
    name: str
    role: Literal["utility", "ipp", "reit", "equipment", "bank"]
    weight: float = 1.0
    thesis: str = ""


class ForecastItem(BaseModel):
    id: str = ""
    signal_type: SignalType
    geo_id: str
    geo_kind: Literal["ba", "county"]
    geo_name: str
    site: str | None = None
    lat: float | None = None
    lon: float | None = None
    h3: str | None = None
    threshold: str = ""
    probability: float = Field(ge=0, le=1)
    previous_probability: float | None = None
    delta: float | None = None
    drivers: list[Driver] = Field(default_factory=list)
    analogs: list[AnalogMatch] = Field(default_factory=list)
    would_increase: list[str] = Field(default_factory=list)
    would_decrease: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    exposed_tickers: list[TickerHit] = Field(default_factory=list)


class ForecastReport(BaseModel):
    as_of: date
    horizon_days: int
    portfolio: str
    items: list[ForecastItem]
    brier: float | None = None
    brier_skill: float | None = None
    notes: list[str] = Field(default_factory=list)


class MapPin(BaseModel):
    id: str
    lat: float
    lon: float
    kind: Literal["forecast", "plant", "campus"]
    label: str
    subtitle: str = ""
    site: str | None = None
    geo_id: str = ""
    geo_kind: str = ""
    signal_type: SignalType | None = None
    probability: float | None = None
    previous_probability: float | None = None
    delta: float | None = None
    rank: int = 0
    exposed_tickers: list[TickerHit] = Field(default_factory=list)
    drivers: list[Driver] = Field(default_factory=list)
    analogs: list[AnalogMatch] = Field(default_factory=list)
    would_increase: list[str] = Field(default_factory=list)
    would_decrease: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    headline: str = ""
    h3: str | None = None


class PulseEvent(BaseModel):
    id: str
    lat: float
    lon: float
    timestamp: datetime
    actor_country: str = "US"
    actor_name: str
    action: str
    theme: str | None = None
    tone: float = 0.0
    location: str | None = None
    geo_id: str | None = None


class FlowArc(BaseModel):
    src_lat: float
    src_lon: float
    dst_lat: float
    dst_lon: float
    src_id: str
    dst_id: str
    weight: float = 1.0
    label: str = ""


class MapPayload(BaseModel):
    as_of: date
    horizon_days: int
    portfolio: str
    pins: list[MapPin]
    plants: list[MapPin] = Field(default_factory=list)
    pulses: list[PulseEvent] = Field(default_factory=list)
    flows: list[FlowArc] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HexSeries(BaseModel):
    h3: list[str]
    week: list[int]
    score: list[float]
    n_events: list[int] = Field(default_factory=list)
    metric: str = "activity"


class BacktestScores(BaseModel):
    n: int
    brier: float
    log_loss: float
    base_rate: float
    baseline_brier: float
    brier_skill: float
    reliability: list[dict] = Field(default_factory=list)
