import type { MapPin, Meta } from "../types";

type Props = {
  meta: Meta | null;
  featured: MapPin | null;
};

export function Hud({ meta, featured }: Props) {
  const skill =
    meta?.brier_skill != null ? `${meta.brier_skill >= 0 ? "+" : ""}${meta.brier_skill.toFixed(2)}` : "—";
  const brier = meta?.brier != null ? meta.brier.toFixed(2) : "—";
  return (
    <header className="hud">
      <div className="brand">
        <h1>GRIDPULSE</h1>
        <span>AI POWER BUILDOUT</span>
      </div>
      <p className="lede">
        {featured?.headline ||
          "Calibrated probabilities of where load, permits, and giga-sites land next."}
      </p>
      <div className="stats">
        <div>
          AS OF <b>{meta?.as_of ?? "—"}</b>
        </div>
        <div>
          BRIER <b>{brier}</b>
        </div>
        <div>
          SKILL <b>{skill}</b>
        </div>
      </div>
      <p className="disclaimer">
        {meta?.disclaimer ||
          "Publisher, not an adviser. Mechanical ticker exposure is not a recommendation."}
      </p>
    </header>
  );
}
