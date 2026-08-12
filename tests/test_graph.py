from datetime import date
from pathlib import Path

from forgecast.graph import Store, dump_timeline
from forgecast.sample import generate_world


def test_store_roundtrip(tmp_path: Path, world):
    db = tmp_path / "t.db"
    store = Store(db)
    store.upsert_events(world.events[:50])
    got = store.events_as_of(date(2025, 1, 1), lookback_days=365 * 20)
    assert len(got) == 50
    rels = store.recent_relations(date(2024, 6, 1), lookback_days=365 * 20)
    assert rels
    lines = dump_timeline(rels, limit=3)
    assert lines
    store.close()
