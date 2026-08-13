from forgecast.config import DEFAULT_PORTFOLIO
from forgecast.exposure import apply_exposure, load_portfolio
from forgecast.schema import ForecastItem, SignalType


def test_ercot_west_hits_vst_nrg_only():
    portfolio = load_portfolio(DEFAULT_PORTFOLIO)
    item = ForecastItem(
        signal_type=SignalType.LOAD_GROWTH,
        geo_id="ERCO-W",
        geo_kind="ba",
        geo_name="ERCOT West",
        probability=0.9,
    )
    item = apply_exposure(item, portfolio)
    tickers = {t.ticker for t in item.exposed_tickers}
    assert tickers == {"VST", "NRG"}
    assert "SO" not in tickers
    assert "EQIX" not in tickers


def test_quiet_geo_does_not_dump_book():
    portfolio = load_portfolio(DEFAULT_PORTFOLIO)
    item = ForecastItem(
        signal_type=SignalType.PERMIT_MW,
        geo_id="35001",
        geo_kind="county",
        geo_name="Bernalillo County, NM",
        probability=0.1,
    )
    item = apply_exposure(item, portfolio)
    tickers = {t.ticker for t in item.exposed_tickers}
    assert tickers <= {"PNM"}
    assert len(tickers) <= 2
