from datetime import datetime

from forgecast.schema import Event, SignalType


def test_event_roundtrip():
    e = Event(
        id="x",
        timestamp=datetime(2024, 6, 1, 12, 0),
        actor="ERCOT West",
        action="reports load",
        action_code="16",
        geo_id="ERCO-W",
        geo_kind="ba",
        lat=32.45,
        lon=-100.4,
        signal_type=SignalType.LOAD_GROWTH,
    )
    clone = Event.model_validate_json(e.model_dump_json())
    assert clone.geo_id == "ERCO-W"
    assert clone.signal_type is SignalType.LOAD_GROWTH
