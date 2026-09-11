import { DataFilterExtension } from "@deck.gl/extensions";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { ArcLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { HexRow, MapPayload, MapPin } from "./types";

const GOLD: [number, number, number, number] = [212, 180, 106, 220];
const CYAN: [number, number, number, number] = [90, 180, 210, 160];
const PLANT: [number, number, number, number] = [180, 80, 70, 200];

const filter = new DataFilterExtension({ filterSize: 1 });

const additive = {
  blendColorSrcFactor: "src-alpha",
  blendColorDstFactor: "one",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one",
} as const;

function heatColor(score: number): [number, number, number, number] {
  const t = Math.min(1, score / 12);
  const r = Math.round(90 + t * 122);
  const g = Math.round(140 + t * 40);
  const b = Math.round(210 - t * 104);
  return [r, g, b, Math.round(40 + t * 140)];
}

export function buildLayers(
  map: MapPayload,
  hexes: HexRow[],
  week: number,
  selectedId: string | null,
  onSelect: (pin: MapPin) => void,
) {
  const forecasts = map.pins.filter((p) => p.kind === "forecast");
  return [
    new H3HexagonLayer<HexRow>({
      id: "hex-heat",
      data: hexes,
      getHexagon: (d) => d.hexagon,
      getFillColor: (d) => heatColor(d.score),
      getElevation: 0,
      extruded: false,
      filled: true,
      stroked: false,
      opacity: 0.85,
      pickable: false,
      parameters: additive,
      extensions: [filter],
      getFilterValue: (d: HexRow) => d.week,
      filterRange: [week - 3, week],
    }),
    new ArcLayer({
      id: "ba-flows",
      data: map.flows,
      getSourcePosition: (d) => [d.src_lon, d.src_lat],
      getTargetPosition: (d) => [d.dst_lon, d.dst_lat],
      getSourceColor: [90, 180, 210, 40],
      getTargetColor: [212, 180, 106, 90],
      getWidth: 1.2,
      greatCircle: true,
      parameters: additive,
    }),
    new ScatterplotLayer({
      id: "plants",
      data: map.plants,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 4500,
      radiusUnits: "meters",
      getFillColor: PLANT,
      getLineColor: [255, 220, 200, 80],
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
      onClick: (info) => info.object && onSelect(info.object as MapPin),
    }),
    new ScatterplotLayer({
      id: "pulses",
      data: map.pulses,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 2200,
      radiusUnits: "meters",
      getFillColor: CYAN,
      pickable: false,
      parameters: additive,
    }),
    new ScatterplotLayer({
      id: "forecasts",
      data: forecasts,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 6000 + (d.probability ?? 0) * 18000,
      radiusUnits: "meters",
      getFillColor: (d) => {
        const p = d.probability ?? 0;
        const glow = d.id === selectedId ? 255 : 220;
        return [glow, 180, 106, Math.round(80 + p * 160)];
      },
      getLineColor: GOLD,
      lineWidthMinPixels: 1.5,
      stroked: true,
      pickable: true,
      parameters: additive,
      onClick: (info) => info.object && onSelect(info.object as MapPin),
    }),
  ];
}
