from forgecast.forecast import WATCHLIST
from forgecast.geo import locate_node, make_pin_id, supplier_pins
from forgecast.schema import DisruptionType


def test_every_watch_item_has_coords():
    for ent in WATCHLIST:
        chokepoint = None
        if ent.disruption is DisruptionType.SHIPPING_THREAT:
            chokepoint = {
                "YE": "Bab el-Mandeb / Red Sea",
                "EG": "Suez Canal",
                "IR": "Strait of Hormuz",
            }.get(ent.country)
        lat, lon, site = locate_node(ent.country, ent.material, chokepoint)
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180
        assert site
        assert make_pin_id(ent.country, ent.material, ent.disruption).startswith(ent.country)


def test_allied_suppliers_are_the_only_extra_pins():
    pins = supplier_pins()
    names = {p.label for p in pins}
    assert "MP Materials" in names
    assert "Lynas" in names
    assert "VSMPO-AVISMA" not in names
