"""Turn scored impacts into a human briefing."""

from __future__ import annotations

from forgecast.city import now_eastern
from forgecast.schema import Place


def weekday_label(when=None) -> str:
    dt = when or now_eastern()
    return dt.strftime("%A")


def kicker(places: list[Place]) -> str:
    names = [p.label for p in places]
    if not names:
        return "Atlanta"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def quiet_copy(n_city: int) -> str:
    if n_city:
        return f"Nothing loud sits on your places right now. {n_city} other city events are on the map."
    return "Quiet near your places. No live city events reached us this refresh."
