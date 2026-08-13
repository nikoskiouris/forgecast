"""Weekly H3 aggregates for the time-scrub heatmap."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from forgecast.config import HEX_PARQUET
from forgecast.geo import cell_for
from forgecast.schema import Event, HexSeries

_EPOCH = date(1970, 1, 5)  # Monday — same origin JS Date.UTC(1970, 0, 5) uses


def week_index(d: date) -> int:
    return (d.toordinal() - _EPOCH.toordinal()) // 7


def week_to_date(index: int) -> date:
    return _EPOCH + timedelta(days=index * 7)


def hex_series(events: list[Event], res: int = 4) -> HexSeries:
    buckets: dict[tuple[str, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for e in events:
        if e.lat is None or e.lon is None:
            continue
        cell = cell_for(e.lat, e.lon, res)
        if not cell:
            continue
        w = week_index(e.timestamp.date())
        score = 1.0 + (1.0 if e.signal_type else 0.0)
        buckets[(cell, w)][0] += score
        buckets[(cell, w)][1] += 1.0
    h3s: list[str] = []
    weeks: list[int] = []
    scores: list[float] = []
    ns: list[int] = []
    for (cell, w), (sc, n) in sorted(buckets.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        h3s.append(cell)
        weeks.append(int(w))
        scores.append(float(sc))
        ns.append(int(n))
    return HexSeries(h3=h3s, week=weeks, score=scores, n_events=ns, metric="activity")


def write_hex_parquet(series: HexSeries, path: Path | None = None) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = path or HEX_PARQUET
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "h3": series.h3,
            "week": series.week,
            "score": series.score,
            "n_events": series.n_events,
        }
    )
    pq.write_table(table, path)
    return path


def read_hex_parquet(path: Path | None = None) -> HexSeries | None:
    path = path or HEX_PARQUET
    if not path.exists():
        return None
    try:
        import duckdb

        con = duckdb.connect()
        rows = con.execute(
            f"SELECT h3, week, score, n_events FROM read_parquet('{path.as_posix()}') ORDER BY week, h3"
        ).fetchall()
        if not rows:
            return HexSeries()
        h3s, weeks, scores, ns = zip(*rows)
        return HexSeries(
            h3=list(h3s),
            week=[int(w) for w in weeks],
            score=[float(s) for s in scores],
            n_events=[int(n) for n in ns],
        )
    except Exception:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        data = table.to_pydict()
        return HexSeries(
            h3=list(data["h3"]),
            week=[int(w) for w in data["week"]],
            score=[float(s) for s in data["score"]],
            n_events=[int(n) for n in data.get("n_events", [0] * len(data["h3"]))],
        )
