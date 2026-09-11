"""Named US grid entities, mechanical ticker book, and sample-world episodes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from forgecast.schema import Entity, Outcome, SignalType, TickerHit

BAS: dict[str, dict] = {
    "PJM": {"name": "PJM Interconnection", "lat": 40.12, "lon": -77.52, "iso": "PJM"},
    "ERCO": {"name": "ERCOT", "lat": 31.0, "lon": -99.9, "iso": "ERCOT"},
    "ERCO-W": {"name": "ERCOT West", "lat": 32.45, "lon": -100.4, "iso": "ERCOT"},
    "MISO": {"name": "MISO", "lat": 41.6, "lon": -90.6, "iso": "MISO"},
    "SOCO": {"name": "Southern Company", "lat": 33.75, "lon": -84.39, "iso": "SOCO"},
    "TVA": {"name": "Tennessee Valley Authority", "lat": 35.96, "lon": -83.92, "iso": "TVA"},
    "NYIS": {"name": "NYISO", "lat": 42.9, "lon": -75.5, "iso": "NYISO"},
    "ISNE": {"name": "ISO-NE", "lat": 42.36, "lon": -71.06, "iso": "ISNE"},
    "SWPP": {"name": "SPP", "lat": 38.0, "lon": -97.5, "iso": "SWPP"},
    "CISO": {"name": "CAISO", "lat": 37.3, "lon": -120.5, "iso": "CISO"},
    "BPAT": {"name": "Bonneville Power", "lat": 45.5, "lon": -122.7, "iso": "BPAT"},
    "FPL": {"name": "Florida Power & Light", "lat": 26.6, "lon": -80.4, "iso": "FPL"},
    "DUK": {"name": "Duke Energy", "lat": 35.78, "lon": -78.64, "iso": "DUK"},
    "PACW": {"name": "PacifiCorp West", "lat": 45.5, "lon": -122.7, "iso": "PACW"},
    "PSCO": {"name": "Public Service of Colorado", "lat": 39.74, "lon": -104.99, "iso": "PSCO"},
    "NEVP": {"name": "NV Energy", "lat": 36.17, "lon": -115.14, "iso": "NEVP"},
    "AZPS": {"name": "Arizona Public Service", "lat": 33.45, "lon": -112.07, "iso": "AZPS"},
    "PNM": {"name": "PNM", "lat": 35.08, "lon": -106.65, "iso": "PNM"},
    "WACM": {"name": "WAPA Colorado-Missouri", "lat": 39.7, "lon": -105.0, "iso": "WACM"},
    "LGEE": {"name": "LG&E / KU", "lat": 38.25, "lon": -85.76, "iso": "LGEE"},
}

COUNTIES: dict[str, dict] = {
    "51107": {"name": "Loudoun County, VA", "lat": 39.08, "lon": -77.64, "state": "VA", "ba": "PJM"},
    "51153": {"name": "Prince William County, VA", "lat": 38.70, "lon": -77.48, "state": "VA", "ba": "PJM"},
    "51059": {"name": "Fairfax County, VA", "lat": 38.85, "lon": -77.28, "state": "VA", "ba": "PJM"},
    "51047": {"name": "Culpeper County, VA", "lat": 38.47, "lon": -77.97, "state": "VA", "ba": "PJM"},
    "24031": {"name": "Montgomery County, MD", "lat": 39.15, "lon": -77.20, "state": "MD", "ba": "PJM"},
    "24033": {"name": "Prince George's County, MD", "lat": 38.83, "lon": -76.85, "state": "MD", "ba": "PJM"},
    "48441": {"name": "Taylor County, TX", "lat": 32.45, "lon": -99.73, "state": "TX", "ba": "ERCO-W"},
    "48367": {"name": "Parker County, TX", "lat": 32.78, "lon": -97.80, "state": "TX", "ba": "ERCO-W"},
    "48439": {"name": "Tarrant County, TX", "lat": 32.75, "lon": -97.33, "state": "TX", "ba": "ERCO"},
    "48113": {"name": "Dallas County, TX", "lat": 32.78, "lon": -96.80, "state": "TX", "ba": "ERCO"},
    "48201": {"name": "Harris County, TX", "lat": 29.76, "lon": -95.37, "state": "TX", "ba": "ERCO"},
    "06065": {"name": "Riverside County, CA", "lat": 33.95, "lon": -117.40, "state": "CA", "ba": "CISO"},
    "06071": {"name": "San Bernardino County, CA", "lat": 34.83, "lon": -116.19, "state": "CA", "ba": "CISO"},
    "04013": {"name": "Maricopa County, AZ", "lat": 33.45, "lon": -112.07, "state": "AZ", "ba": "AZPS"},
    "32003": {"name": "Clark County, NV", "lat": 36.17, "lon": -115.14, "state": "NV", "ba": "NEVP"},
    "49035": {"name": "Salt Lake County, UT", "lat": 40.67, "lon": -111.89, "state": "UT", "ba": "PACW"},
    "08031": {"name": "Denver County, CO", "lat": 39.74, "lon": -104.99, "state": "CO", "ba": "PSCO"},
    "17031": {"name": "Cook County, IL", "lat": 41.84, "lon": -87.68, "state": "IL", "ba": "PJM"},
    "39049": {"name": "Franklin County, OH", "lat": 39.96, "lon": -83.00, "state": "OH", "ba": "PJM"},
    "42101": {"name": "Philadelphia County, PA", "lat": 39.95, "lon": -75.16, "state": "PA", "ba": "PJM"},
    "36061": {"name": "New York County, NY", "lat": 40.78, "lon": -73.97, "state": "NY", "ba": "NYIS"},
    "25025": {"name": "Suffolk County, MA", "lat": 42.36, "lon": -71.06, "state": "MA", "ba": "ISNE"},
    "53033": {"name": "King County, WA", "lat": 47.61, "lon": -122.33, "state": "WA", "ba": "BPAT"},
    "41051": {"name": "Multnomah County, OR", "lat": 45.51, "lon": -122.65, "state": "OR", "ba": "BPAT"},
    "13121": {"name": "Fulton County, GA", "lat": 33.75, "lon": -84.39, "state": "GA", "ba": "SOCO"},
    "47037": {"name": "Davidson County, TN", "lat": 36.16, "lon": -86.78, "state": "TN", "ba": "TVA"},
    "12086": {"name": "Miami-Dade County, FL", "lat": 25.76, "lon": -80.19, "state": "FL", "ba": "FPL"},
    "48215": {"name": "Hidalgo County, TX", "lat": 26.39, "lon": -98.18, "state": "TX", "ba": "ERCO"},
    "48141": {"name": "El Paso County, TX", "lat": 31.76, "lon": -106.49, "state": "TX", "ba": "ERCO-W"},
    "35001": {"name": "Bernalillo County, NM", "lat": 35.08, "lon": -106.65, "state": "NM", "ba": "PNM"},
}

PLACE_HINTS: dict[str, str] = {
    "ashburn": "51107",
    "loudoun": "51107",
    "manassas": "51153",
    "prince william": "51153",
    "culpeper": "51047",
    "abilene": "48441",
    "taylor county": "48441",
    "ercot west": "ERCO-W",
    "ercot": "ERCO",
    "pjm": "PJM",
}

TICKERS: dict[str, list[str]] = {
    "PJM": ["D", "AEP", "EXC", "FE", "PEG", "PPL", "CEG"],
    "ERCO": ["VST", "NRG", "NEE"],
    "ERCO-W": ["VST", "NRG"],
    "MISO": ["AEP", "EXC", "EIX"],
    "SOCO": ["SO", "DUK"],
    "TVA": ["SO", "DUK"],
    "NYIS": ["CEG", "NEE"],
    "ISNE": ["ES", "NEE"],
    "SWPP": ["AEP", "XEL"],
    "CISO": ["EIX", "PCG", "SRE"],
    "BPAT": ["POR"],
    "FPL": ["NEE"],
    "DUK": ["DUK"],
    "PACW": ["POR"],
    "PSCO": ["XEL"],
    "NEVP": ["NEE"],
    "AZPS": ["PNW"],
    "PNM": ["PNM"],
    "WACM": ["XEL"],
    "LGEE": ["PPL"],
    "51107": ["D", "DLR", "EQIX", "IRM", "ETN", "PWR", "VRT", "GEV"],
    "51153": ["D", "DLR", "EQIX", "ETN", "VRT"],
    "51059": ["D", "DLR", "EQIX"],
    "51047": ["D", "DLR", "EQIX", "ETN", "VRT", "USB"],
    "24031": ["D", "EXC", "DLR"],
    "24033": ["EXC", "D"],
    "48441": ["VST", "NRG", "PWR", "DLR", "ETN", "VRT"],
    "48367": ["VST", "NRG", "PWR"],
    "48439": ["VST", "NRG", "DLR"],
    "48113": ["VST", "NRG", "DLR"],
    "48201": ["VST", "NRG", "NEE", "PWR"],
    "48215": ["VST", "NRG"],
    "48141": ["VST", "PNM"],
    "06065": ["EIX", "SRE", "DLR", "EQIX"],
    "06071": ["EIX", "SRE", "DLR"],
    "04013": ["PNW", "DLR", "EQIX", "ETN"],
    "32003": ["EQIX", "DLR"],
    "49035": ["IRM"],
    "08031": ["XEL", "DLR"],
    "35001": ["PNM"],
    "17031": ["EXC", "AEP", "EQIX", "DLR"],
    "39049": ["AEP", "FE", "EQIX"],
    "42101": ["EXC", "PPL", "EQIX"],
    "36061": ["CEG", "EQIX", "DLR", "IRM"],
    "25025": ["ES", "EQIX", "DLR"],
    "53033": ["POR", "EQIX", "IRM"],
    "41051": ["POR", "EQIX"],
    "13121": ["SO", "EQIX", "DLR"],
    "47037": ["SO", "DUK"],
    "12086": ["NEE", "EQIX", "DLR"],
}

TICKER_BOOK: dict[str, tuple[str, str]] = {
    "D": ("Dominion Energy", "utility"),
    "AEP": ("American Electric Power", "utility"),
    "SO": ("Southern Company", "utility"),
    "DUK": ("Duke Energy", "utility"),
    "EXC": ("Exelon", "utility"),
    "FE": ("FirstEnergy", "utility"),
    "PEG": ("PSEG", "utility"),
    "PPL": ("PPL", "utility"),
    "ES": ("Eversource", "utility"),
    "EIX": ("Edison International", "utility"),
    "PCG": ("PG&E", "utility"),
    "SRE": ("Sempra", "utility"),
    "XEL": ("Xcel Energy", "utility"),
    "NEE": ("NextEra Energy", "utility"),
    "POR": ("Portland General Electric", "utility"),
    "PNW": ("Pinnacle West", "utility"),
    "PNM": ("PNM Resources", "utility"),
    "VST": ("Vistra", "ipp"),
    "NRG": ("NRG Energy", "ipp"),
    "CEG": ("Constellation Energy", "ipp"),
    "DLR": ("Digital Realty", "reit"),
    "EQIX": ("Equinix", "reit"),
    "IRM": ("Iron Mountain", "reit"),
    "ETN": ("Eaton", "equipment"),
    "PWR": ("Quanta Services", "equipment"),
    "VRT": ("Vertiv", "equipment"),
    "GEV": ("GE Vernova", "equipment"),
    "USB": ("U.S. Bancorp", "bank"),
    "FITB": ("Fifth Third", "bank"),
}

PLANTS: list[dict] = [
    {"id": "plant-vst-odessa", "name": "Odessa combined cycle", "lat": 31.85, "lon": -102.37, "ba": "ERCO-W", "operator": "Vistra"},
    {"id": "plant-nrg-waelder", "name": "Waelder peakers", "lat": 29.69, "lon": -97.30, "ba": "ERCO", "operator": "NRG"},
    {"id": "plant-ceg-calvert", "name": "Calvert Cliffs", "lat": 38.43, "lon": -76.44, "ba": "PJM", "operator": "Constellation"},
    {"id": "plant-d-northanna", "name": "North Anna", "lat": 38.06, "lon": -77.79, "ba": "PJM", "operator": "Dominion"},
    {"id": "plant-aep-mountaineer", "name": "Mountaineer", "lat": 38.98, "lon": -81.93, "ba": "PJM", "operator": "AEP"},
    {"id": "plant-nee-turkey", "name": "Turkey Point", "lat": 25.43, "lon": -80.33, "ba": "FPL", "operator": "NextEra"},
    {"id": "plant-so-vogtle", "name": "Vogtle", "lat": 33.14, "lon": -81.76, "ba": "SOCO", "operator": "Southern"},
]


@dataclass(frozen=True)
class Episode:
    id: str
    geo_id: str
    signal: SignalType
    start: date
    peak: date
    intensity: float
    analog_label: str


# Peaks after demo as_of (2026-06-01) so ramps are visible without leaking labels into training.
EPISODES: list[Episode] = [
    Episode("loudoun_2023", "51107", SignalType.PERMIT_MW, date(2023, 2, 1), date(2023, 8, 15), 0.95, "Loudoun 2023 campus wave"),
    Episode("loudoun_2024", "51107", SignalType.GIGA_SITE, date(2024, 1, 10), date(2024, 6, 1), 0.88, "Loudoun 2024 giga-site"),
    Episode("pwc_2024", "51153", SignalType.PERMIT_MW, date(2024, 3, 1), date(2024, 9, 20), 0.82, "Prince William 2024 permits"),
    Episode("ercow_2025", "ERCO-W", SignalType.LOAD_GROWTH, date(2025, 1, 15), date(2025, 7, 1), 0.97, "ERCOT-West 2025 breakout"),
    Episode("abilene_2025", "48441", SignalType.PERMIT_MW, date(2025, 2, 1), date(2025, 8, 10), 0.91, "Abilene 2025 campus permits"),
    Episode("abilene_giga_2025", "48441", SignalType.GIGA_SITE, date(2025, 4, 1), date(2025, 9, 15), 0.86, "Abilene 2025 giga-site"),
    Episode("pjm_2024", "PJM", SignalType.LOAD_GROWTH, date(2024, 5, 1), date(2024, 11, 1), 0.78, "PJM 2024 load step-up"),
    Episode("maricopa_2024", "04013", SignalType.PERMIT_MW, date(2024, 6, 1), date(2024, 12, 1), 0.70, "Maricopa 2024 industrial"),
    Episode("clark_2023", "32003", SignalType.GIGA_SITE, date(2023, 8, 1), date(2024, 1, 15), 0.65, "Clark 2023 campus"),
    Episode("ciso_2024", "CISO", SignalType.LOAD_GROWTH, date(2024, 2, 1), date(2024, 8, 1), 0.60, "CAISO 2024 summer load"),
    Episode("cook_2024", "17031", SignalType.PERMIT_MW, date(2024, 4, 1), date(2024, 10, 1), 0.55, "Cook County 2024"),
    Episode("fulton_2025", "13121", SignalType.PERMIT_MW, date(2025, 3, 1), date(2025, 9, 1), 0.58, "Fulton 2025 industrial"),
    Episode("king_2024", "53033", SignalType.GIGA_SITE, date(2024, 7, 1), date(2025, 1, 1), 0.52, "King County 2024 campus"),
    Episode("ercow_2026", "ERCO-W", SignalType.LOAD_GROWTH, date(2026, 1, 15), date(2026, 9, 20), 0.96, "ERCOT-West 2026 continuation"),
    Episode("abilene_permits_2026", "48441", SignalType.PERMIT_MW, date(2026, 2, 1), date(2026, 10, 5), 0.93, "Abilene 2026 campus permits"),
    Episode("culpeper_2026", "51047", SignalType.GIGA_SITE, date(2026, 1, 1), date(2026, 11, 1), 0.84, "Culpeper 2026 giga-site"),
]


def watchlist() -> list[Entity]:
    items: list[Entity] = []
    for ba in BAS:
        items.append(Entity(geo_id=ba, geo_kind="ba", signal=SignalType.LOAD_GROWTH))
    for fips in COUNTIES:
        items.append(Entity(geo_id=fips, geo_kind="county", signal=SignalType.PERMIT_MW))
        items.append(Entity(geo_id=fips, geo_kind="county", signal=SignalType.GIGA_SITE))
    return items


def train_watchlist() -> list[Entity]:
    """Short subset so first forecast() stays fast enough for tests."""
    return [
        Entity("PJM", "ba", SignalType.LOAD_GROWTH),
        Entity("ERCO", "ba", SignalType.LOAD_GROWTH),
        Entity("ERCO-W", "ba", SignalType.LOAD_GROWTH),
        Entity("CISO", "ba", SignalType.LOAD_GROWTH),
        Entity("MISO", "ba", SignalType.LOAD_GROWTH),
        Entity("SOCO", "ba", SignalType.LOAD_GROWTH),
        Entity("51107", "county", SignalType.PERMIT_MW),
        Entity("48441", "county", SignalType.PERMIT_MW),
        Entity("51153", "county", SignalType.PERMIT_MW),
        Entity("04013", "county", SignalType.PERMIT_MW),
        Entity("51107", "county", SignalType.GIGA_SITE),
        Entity("48441", "county", SignalType.GIGA_SITE),
        Entity("51047", "county", SignalType.GIGA_SITE),
        Entity("32003", "county", SignalType.GIGA_SITE),
    ]


def place_name(geo_id: str) -> str:
    if geo_id in BAS:
        return str(BAS[geo_id]["name"])
    if geo_id in COUNTIES:
        return str(COUNTIES[geo_id]["name"])
    return geo_id


def coords(geo_id: str) -> tuple[float, float]:
    if geo_id in BAS:
        return float(BAS[geo_id]["lat"]), float(BAS[geo_id]["lon"])
    if geo_id in COUNTIES:
        return float(COUNTIES[geo_id]["lat"]), float(COUNTIES[geo_id]["lon"])
    return 39.0, -98.0


def geo_kind_of(geo_id: str) -> str:
    if geo_id in BAS:
        return "ba"
    return "county"


def tickers_for(geo_id: str) -> list[str]:
    return list(TICKERS.get(geo_id, []))


def ticker_hit(symbol: str) -> TickerHit | None:
    meta = TICKER_BOOK.get(symbol)
    if not meta:
        return None
    name, role = meta
    return TickerHit(ticker=symbol, name=name, role=role)  # type: ignore[arg-type]


def outcomes_from_episodes() -> list[Outcome]:
    out: list[Outcome] = []
    for ep in EPISODES:
        out.append(
            Outcome(
                occurred_on=ep.peak,
                geo_id=ep.geo_id,
                geo_kind=geo_kind_of(ep.geo_id),  # type: ignore[arg-type]
                signal_type=ep.signal,
                name=ep.analog_label,
            )
        )
    return out


def resolve_geo(name: str | None, lat: float | None = None, lon: float | None = None) -> tuple[str | None, str | None]:
    blob = (name or "").lower()
    for hint, geo_id in PLACE_HINTS.items():
        if hint in blob:
            return geo_id, geo_kind_of(geo_id)
    for fips, meta in COUNTIES.items():
        county = str(meta["name"]).split(",")[0].lower()
        if county in blob:
            return fips, "county"
    for ba, meta in BAS.items():
        if str(meta["name"]).lower() in blob or ba.lower() in blob:
            return ba, "ba"
    if lat is None or lon is None:
        return None, None
    best_id = None
    best_d = 1e9
    for geo_id in list(COUNTIES) + list(BAS):
        glat, glon = coords(geo_id)
        d = (glat - lat) ** 2 + (glon - lon) ** 2
        if d < best_d:
            best_d = d
            best_id = geo_id
    if best_id is None or best_d > 4.0:
        return None, None
    return best_id, geo_kind_of(best_id)
