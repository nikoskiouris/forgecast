from datetime import datetime

from forgecast.schema import DisruptionType, Event


def test_event_roundtrip():
    e = Event(
        id="x",
        timestamp=datetime(2024, 6, 1, 12, 0),
        actor="CN",
        actor_country="CN",
        action="threatens",
        action_code="13",
        material="gallium",
        disruption_type=DisruptionType.EXPORT_RESTRICTION,
    )
    clone = Event.model_validate_json(e.model_dump_json())
    assert clone.material == "gallium"
    assert clone.disruption_type is DisruptionType.EXPORT_RESTRICTION
