from forgecast.ingest.cameo import action_label, root_code, signal_for_theme
from forgecast.ingest.gdelt import parse_gdelt_csv
from forgecast.schema import SignalType


def _row(overrides: dict | None = None) -> str:
    cols = [""] * 58
    cols[0] = "99"
    cols[1] = "20230801"
    cols[6] = "CHINA"
    cols[7] = "CHN"
    cols[16] = "UNITED STATES"
    cols[17] = "USA"
    cols[26] = "163"
    cols[30] = "-8.0"
    cols[34] = "-4.2"
    cols[50] = "Ashburn, Virginia, United States"
    cols[51] = "US"
    cols[53] = "39.0438"
    cols[54] = "-77.4874"
    cols[57] = "https://example.com/data-center-campus-megawatt"
    for k, v in (overrides or {}).items():
        cols[k] = v
    return "\t".join(cols)


def test_cameo_root():
    assert root_code("1631") == "163"
    assert action_label("13") == "threatens"
    assert signal_for_theme(text="new data center campus") is SignalType.GIGA_SITE


def test_parse_keeps_grid_geo_and_drops_talks():
    talks = _row(
        {
            26: "04",
            6: "STATE DEPT",
            50: "Washington, DC, United States",
            53: "38.9",
            54: "-77.0",
            57: "https://example.com/talks",
        }
    )
    raw = _row() + "\n" + talks
    events = parse_gdelt_csv(raw)
    assert len(events) == 1
    assert "Ashburn" in (events[0].location or "")
    assert events[0].lat == 39.0438
    assert events[0].lon == -77.4874
    assert events[0].geo_id == "51107"
