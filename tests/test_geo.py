from forgecast.explain import headline
from forgecast.forecast import WATCHLIST
from forgecast.geo import locate, make_pin_id
from forgecast.schema import ForecastItem, SignalType
from forgecast.staticdata import coords


def test_every_watch_item_has_coords():
    for ent in WATCHLIST:
        lat, lon, site = locate(ent.geo_id)
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180
        assert site
        assert make_pin_id(ent.geo_id, ent.signal).startswith(ent.geo_id)
        plat, plon = coords(ent.geo_id)
        assert plat == lat


def test_headline_grammar():
    permit = ForecastItem(
        signal_type=SignalType.PERMIT_MW,
        geo_id="48441",
        geo_kind="county",
        geo_name="Taylor County, TX",
        probability=0.9,
    )
    text = headline(permit, 180)
    assert "permit-MW in Taylor County" in text
    giga = ForecastItem(
        signal_type=SignalType.GIGA_SITE,
        geo_id="51047",
        geo_kind="county",
        geo_name="Culpeper County, VA",
        probability=0.9,
    )
    assert "announced in Culpeper County" in headline(giga, 180)
