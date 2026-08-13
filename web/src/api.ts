import type { HexRow, HexSeries, MapPayload, Meta } from "./types";

const BASE = import.meta.env.BASE_URL || "/";

async function load<T>(apiPath: string, file: string): Promise<T> {
  try {
    const res = await fetch(`/api/${apiPath}`);
    if (res.ok) return (await res.json()) as T;
  } catch {
    /* Pages has no API — fall through to baked JSON */
  }
  const res = await fetch(`${BASE}data/${file}`);
  if (!res.ok) throw new Error(`failed to load ${file}`);
  return (await res.json()) as T;
}

export function loadMeta(): Promise<Meta> {
  return load<Meta>("meta", "meta.json");
}

export function loadMap(): Promise<MapPayload> {
  return load<MapPayload>("map", "map.json");
}

export function loadHex(): Promise<HexSeries> {
  return load<HexSeries>("hex/4", "hex.json");
}

export function rowsFromHex(series: HexSeries): HexRow[] {
  return series.h3.map((hexagon, i) => ({
    hexagon,
    week: series.week[i],
    score: series.score[i],
  }));
}
