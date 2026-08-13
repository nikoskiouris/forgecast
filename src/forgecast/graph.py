"""SQLite store for events and temporal relations."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from forgecast.schema import Event, Relation


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.conn = _connect(path)
        self._init()

    def _init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                actor TEXT,
                actor_country TEXT,
                action TEXT,
                action_code TEXT,
                target TEXT,
                target_country TEXT,
                theme TEXT,
                location TEXT,
                lat REAL,
                lon REAL,
                h3 TEXT,
                geo_id TEXT,
                geo_kind TEXT,
                goldstein REAL,
                tone REAL,
                source_url TEXT,
                source TEXT,
                signal_type TEXT,
                raw TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_geo ON events(geo_id);

            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY,
                ts TEXT NOT NULL,
                subject TEXT,
                predicate TEXT,
                object TEXT,
                theme TEXT,
                confidence REAL,
                event_id TEXT,
                UNIQUE(event_id, predicate)
            );
            CREATE INDEX IF NOT EXISTS idx_rel_ts ON relations(ts);
            """
        )
        self.conn.commit()

    def upsert_events(self, events: list[Event]) -> int:
        rows = [
            (
                e.id,
                e.timestamp.isoformat(),
                e.actor,
                e.actor_country,
                e.action,
                e.action_code,
                e.target,
                e.target_country,
                e.theme,
                e.location,
                e.lat,
                e.lon,
                e.h3,
                e.geo_id,
                e.geo_kind,
                e.goldstein,
                e.tone,
                e.source_url,
                e.source,
                e.signal_type.value if e.signal_type else None,
                e.model_dump_json(),
            )
            for e in events
        ]
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO events (
                id, ts, actor, actor_country, action, action_code, target,
                target_country, theme, location, lat, lon, h3, geo_id, geo_kind,
                goldstein, tone, source_url, source, signal_type, raw
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        ids = [(e.id,) for e in events]
        if ids:
            self.conn.executemany("DELETE FROM relations WHERE event_id = ?", ids)
        rels = [r for e in events for r in relations_from_event(e)]
        if rels:
            self.conn.executemany(
                """
                INSERT OR IGNORE INTO relations
                    (ts, subject, predicate, object, theme, confidence, event_id)
                VALUES (?,?,?,?,?,?,?)
                """,
                [
                    (
                        r.timestamp.isoformat(),
                        r.subject,
                        r.predicate,
                        r.object,
                        r.theme,
                        r.confidence,
                        r.event_id,
                    )
                    for r in rels
                ],
            )
        self.conn.commit()
        return len(events)

    def events_as_of(
        self,
        as_of: date,
        lookback_days: int = 365 * 8,
        geo_id: str | None = None,
    ) -> list[Event]:
        start = (as_of - timedelta(days=lookback_days)).isoformat()
        end = datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59).isoformat()
        sql = "SELECT raw FROM events WHERE ts >= ? AND ts <= ?"
        args: list[object] = [start, end]
        if geo_id:
            sql += " AND geo_id = ?"
            args.append(geo_id)
        sql += " ORDER BY ts"
        rows = self.conn.execute(sql, args).fetchall()
        return [Event.model_validate_json(r["raw"]) for r in rows]

    def recent_relations(self, as_of: date, lookback_days: int = 180) -> list[Relation]:
        start = (as_of - timedelta(days=lookback_days)).isoformat()
        end = as_of.isoformat() + "T23:59:59"
        rows = self.conn.execute(
            "SELECT ts, subject, predicate, object, theme, confidence, event_id "
            "FROM relations WHERE ts >= ? AND ts <= ? ORDER BY ts",
            (start, end),
        ).fetchall()
        return [
            Relation(
                timestamp=datetime.fromisoformat(r["ts"]),
                subject=r["subject"],
                predicate=r["predicate"],
                object=r["object"],
                theme=r["theme"],
                confidence=r["confidence"],
                event_id=r["event_id"],
            )
            for r in rows
        ]

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def close(self) -> None:
        self.conn.close()


def relations_from_event(event: Event) -> list[Relation]:
    pred = event.action.replace(" ", "_").upper()
    obj = event.geo_id or event.target or "UNK"
    return [
        Relation(
            timestamp=event.timestamp,
            subject=event.geo_id or event.actor,
            predicate=pred,
            object=str(obj),
            theme=event.theme,
            confidence=1.0,
            event_id=event.id,
        )
    ]


def dump_timeline(relations: list[Relation], limit: int = 12) -> list[str]:
    lines = []
    for r in relations[-limit:]:
        theme = f" → {r.theme}" if r.theme else ""
        lines.append(
            f"{r.timestamp.date()}  {r.subject} → {r.predicate.lower()} → {r.object}{theme}"
        )
    return lines
