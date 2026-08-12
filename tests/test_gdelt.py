from forgecast.ingest.gdelt import parse_gdelt_csv
from forgecast.ingest.cameo import action_label, root_code


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
    cols[51] = "Beijing, China"
    cols[57] = "https://example.com/gallium-export-controls"
    for k, v in (overrides or {}).items():
        cols[k] = v
    return "\t".join(cols)


def test_cameo_root():
    assert root_code("1631") == "163"
    assert action_label("13") == "threatens"


def test_parse_filters_and_tags_material():
    raw = _row() + "\n" + _row({26: "04", 57: "https://example.com/talks"})
    events = parse_gdelt_csv(raw)
    assert len(events) == 1
    assert events[0].material == "gallium"
    assert events[0].actor_country == "CN"
