import type { MapPin } from "../types";

type Props = {
  pin: MapPin | null;
};

export function Drilldown({ pin }: Props) {
  if (!pin) {
    return (
      <aside className="drill">
        <div className="kicker">Select a node</div>
        <h2>Click a gold pulse</h2>
        <p>Forecast pins carry probability, analogs, and mechanical ticker exposure.</p>
      </aside>
    );
  }
  const pct = pin.probability != null ? `${Math.round(pin.probability * 100)}%` : "—";
  return (
    <aside className="drill">
      <div className="kicker">{pin.signal_type?.replaceAll("_", " ") || pin.kind}</div>
      <h2>{pin.label}</h2>
      <div className="prob">{pct}</div>
      <p>{pin.headline || pin.subtitle}</p>
      {pin.exposed_tickers.length > 0 && (
        <>
          <div className="kicker">Exposed</div>
          <div className="tickers">
            {pin.exposed_tickers.map((t) => (
              <span className="chip" key={t.ticker} title={t.name}>
                {t.ticker}
              </span>
            ))}
          </div>
        </>
      )}
      {pin.analogs.length > 0 && (
        <>
          <div className="kicker">Analog</div>
          <ul>
            {pin.analogs.map((a) => (
              <li key={a.name}>
                {a.name} ({a.year}) — {Math.round(a.similarity * 100)}% similar. {a.difference}
              </li>
            ))}
          </ul>
        </>
      )}
      {pin.drivers.length > 0 && (
        <>
          <div className="kicker">Drivers</div>
          <ul>
            {pin.drivers.map((d) => (
              <li key={d.indicator}>
                {d.direction === "up" ? "↑" : "↓"} {d.indicator}: {d.detail}
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
