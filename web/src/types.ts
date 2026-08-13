export type SignalType = "load_growth" | "permit_mw" | "giga_site";

export type TickerHit = {
  ticker: string;
  name: string;
  role: string;
  weight?: number;
  thesis?: string;
};

export type Driver = {
  indicator: string;
  direction: "up" | "down";
  detail: string;
};

export type AnalogMatch = {
  name: string;
  similarity: number;
  year: number;
  geo_id: string;
  geo_name: string;
  outcome: string;
  difference: string;
};

export type MapPin = {
  id: string;
  lat: number;
  lon: number;
  kind: "forecast" | "plant" | "campus";
  label: string;
  subtitle: string;
  geo_id: string;
  geo_kind: string;
  signal_type: SignalType | null;
  probability: number | null;
  previous_probability: number | null;
  delta: number | null;
  rank: number;
  exposed_tickers: TickerHit[];
  drivers: Driver[];
  analogs: AnalogMatch[];
  would_increase: string[];
  would_decrease: string[];
  sources: string[];
  headline: string;
  h3: string | null;
};

export type PulseEvent = {
  id: string;
  lat: number;
  lon: number;
  timestamp: string;
  actor_name: string;
  action: string;
  theme: string | null;
  location: string | null;
  geo_id: string | null;
};

export type FlowArc = {
  src_lat: number;
  src_lon: number;
  dst_lat: number;
  dst_lon: number;
  src_id: string;
  dst_id: string;
  weight: number;
  label: string;
};

export type MapPayload = {
  as_of: string;
  horizon_days: number;
  portfolio: string;
  pins: MapPin[];
  plants: MapPin[];
  pulses: PulseEvent[];
  flows: FlowArc[];
  notes: string[];
};

export type HexSeries = {
  h3: string[];
  week: number[];
  score: number[];
  n_events: number[];
  metric: string;
};

export type Meta = {
  product: string;
  version: string;
  as_of: string;
  horizon_days: number;
  week?: number;
  n?: number;
  brier?: number;
  brier_skill?: number;
  base_rate?: number;
  disclaimer?: string;
};

export type HexRow = {
  hexagon: string;
  week: number;
  score: number;
};
