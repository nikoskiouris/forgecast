from forgecast.config import DEFAULT_PORTFOLIO
from forgecast.exposure import apply_exposure, load_portfolio
from forgecast.schema import DisruptionType, ForecastItem


def test_titanium_hits_f35_and_vsmpo():
    portfolio = load_portfolio(DEFAULT_PORTFOLIO)
    item = ForecastItem(
        disruption_type=DisruptionType.EXPORT_RESTRICTION,
        actor_country="RU",
        actor_name="Russia",
        material="titanium",
        probability=0.31,
    )
    item = apply_exposure(item, portfolio)
    assert any("F-35" in p for p in item.exposed_programs)
    assert any("VSMPO" in s for s in item.exposed_suppliers)


def test_shipping_exposes_all_programs():
    portfolio = load_portfolio(DEFAULT_PORTFOLIO)
    item = ForecastItem(
        disruption_type=DisruptionType.SHIPPING_THREAT,
        actor_country="YE",
        actor_name="Yemen",
        chokepoint="Red Sea",
        probability=0.4,
    )
    item = apply_exposure(item, portfolio)
    assert len(item.exposed_programs) >= 3
