import { useEffect, useMemo, useState } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { Map, useControl } from "react-map-gl/maplibre";
import { loadHex, loadMap, loadMeta, rowsFromHex } from "./api";
import { Drilldown } from "./components/Drilldown";
import { Hud } from "./components/Hud";
import { TimeScrubber } from "./components/TimeScrubber";
import { buildLayers } from "./layers";
import type { HexRow, MapPayload, MapPin, Meta } from "./types";
import "maplibre-gl/dist/maplibre-gl.css";

const STYLE = "https://tiles.openfreemap.org/styles/dark";

function DeckOverlay({ layers }: { layers: unknown[] }) {
  const overlay = useControl<MapboxOverlay>(
    () => new MapboxOverlay({ interleaved: true, layers: layers as never[] }),
  );
  overlay.setProps({ layers: layers as never[] });
  return null;
}

function weekLabel(week: number): string {
  const ms = Date.UTC(1970, 0, 5) + week * 7 * 86_400_000;
  return new Date(ms).toISOString().slice(0, 10);
}

export function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [map, setMap] = useState<MapPayload | null>(null);
  const [hexes, setHexes] = useState<HexRow[]>([]);
  const [week, setWeek] = useState<number | null>(null);
  const [selected, setSelected] = useState<MapPin | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([loadMeta(), loadMap(), loadHex()])
      .then(([m, payload, hex]) => {
        setMeta(m);
        setMap(payload);
        const rows = rowsFromHex(hex);
        setHexes(rows);
        const weeks = rows.map((r) => r.week);
        const fallback = m.week ?? (weeks.length ? Math.max(...weeks) : 0);
        setWeek(fallback);
        setSelected(payload.pins[0] ?? null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const weekRange = useMemo(() => {
    if (!hexes.length) return { min: 0, max: 1 };
    const weeks = hexes.map((r) => r.week);
    return { min: Math.min(...weeks), max: Math.max(...weeks) };
  }, [hexes]);

  const layers = useMemo(() => {
    if (!map || week == null) return [];
    return buildLayers(map, hexes, week, selected?.id ?? null, setSelected);
  }, [map, hexes, week, selected]);

  if (error) return <div className="status">FAILED · {error}</div>;
  if (!map || week == null) return <div className="status">GRIDPULSE</div>;

  return (
    <div className="map-root">
      <Map
        mapStyle={STYLE}
        initialViewState={{ longitude: -97.8, latitude: 38.6, zoom: 3.55, pitch: 28, bearing: -8 }}
        style={{ width: "100%", height: "100%" }}
        attributionControl={false}
      >
        <DeckOverlay layers={layers} />
      </Map>
      <div className="grain" />
      <Hud meta={meta} featured={selected} />
      <Drilldown pin={selected} />
      <TimeScrubber
        min={weekRange.min}
        max={weekRange.max}
        value={week}
        label={weekLabel(week)}
        onChange={setWeek}
      />
    </div>
  );
}
