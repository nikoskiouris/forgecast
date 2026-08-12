"""Static DIB context: critical materials, exporters, alliances, named episodes."""

from __future__ import annotations

from datetime import date

from forgecast.schema import DisruptionType, Outcome

COUNTRY_NAMES = {
    "CN": "China",
    "RU": "Russia",
    "IR": "Iran",
    "YE": "Yemen",
    "UA": "Ukraine",
    "TW": "Taiwan",
    "CD": "DR Congo",
    "ID": "Indonesia",
    "ZA": "South Africa",
    "AU": "Australia",
    "CL": "Chile",
    "MM": "Myanmar",
    "TR": "Turkey",
    "EG": "Egypt",
    "US": "United States",
    "JP": "Japan",
    "DE": "Germany",
    "KR": "South Korea",
    "GB": "United Kingdom",
    "AU2": "Australia",
}

MATERIALS = [
    "titanium",
    "rare_earths",
    "gallium",
    "germanium",
    "antimony",
    "graphite",
    "cobalt",
    "nickel",
    "palladium",
    "neon",
    "semiconductors",
    "tungsten",
    "beryllium",
    "aluminum",
    "steel",
    "carbon_fiber",
]

# Approximate exporter concentration (0-1). Higher = more chokepoint risk.
EXPORTER_SHARE = {
    ("CN", "rare_earths"): 0.70,
    ("CN", "gallium"): 0.98,
    ("CN", "germanium"): 0.68,
    ("CN", "antimony"): 0.56,
    ("CN", "graphite"): 0.65,
    ("CN", "tungsten"): 0.82,
    ("CN", "aluminum"): 0.55,
    ("RU", "titanium"): 0.30,
    ("RU", "palladium"): 0.40,
    ("RU", "nickel"): 0.09,
    ("UA", "neon"): 0.50,
    ("CD", "cobalt"): 0.70,
    ("ID", "nickel"): 0.48,
    ("ZA", "palladium"): 0.35,
    ("TW", "semiconductors"): 0.60,
    ("CL", "aluminum"): 0.05,
    ("MM", "rare_earths"): 0.15,
    ("AU", "rare_earths"): 0.08,
    ("AU", "lithium"): 0.25,
}

US_ALLIES = {"US", "JP", "DE", "KR", "GB", "AU", "TW"}

# Trade interdependence with the US / allies (0-1). Time-aware via year.
def interdependence(country: str, year: int) -> float:
    base = {
        "CN": 0.82,
        "RU": 0.35 if year < 2022 else 0.12,
        "IR": 0.05,
        "YE": 0.02,
        "UA": 0.28,
        "TW": 0.75,
        "CD": 0.18,
        "ID": 0.40,
        "ZA": 0.32,
        "AU": 0.70,
        "CL": 0.45,
        "MM": 0.10,
        "TR": 0.48,
        "EG": 0.30,
        "JP": 0.88,
        "DE": 0.85,
        "KR": 0.80,
        "GB": 0.90,
        "US": 1.0,
    }.get(country, 0.2)
    return base


# Named historical episodes used as analog anchors and outcome labels.
EPISODES: list[dict] = [
    {
        "id": "cn_re_2010",
        "name": "China–Japan rare earth export cutoff",
        "start": date(2010, 7, 1),
        "peak": date(2010, 10, 8),
        "country": "CN",
        "material": "rare_earths",
        "disruption": DisruptionType.EXPORT_RESTRICTION,
        "notes": "After the Senkaku/Diaoyu incident, China halted rare earth shipments to Japan.",
        "sources": [
            "https://www.cfr.org/backgrounder/chinas-rare-earth-industry",
            "https://www.usgs.gov/centers/national-minerals-information-center/rare-earths-statistics-and-information",
        ],
    },
    {
        "id": "suez_2021",
        "name": "Ever Given blockage of the Suez Canal",
        "start": date(2021, 3, 1),
        "peak": date(2021, 3, 23),
        "country": "EG",
        "material": None,
        "disruption": DisruptionType.SHIPPING_THREAT,
        "notes": "A grounded container ship closed the canal for six days.",
        "sources": ["https://en.wikipedia.org/wiki/2021_Suez_Canal_obstruction"],
    },
    {
        "id": "ru_ti_2022",
        "name": "Russia invasion shock to aerospace titanium",
        "start": date(2021, 11, 1),
        "peak": date(2022, 2, 24),
        "country": "RU",
        "material": "titanium",
        "disruption": DisruptionType.EXPORT_RESTRICTION,
        "notes": "VSMPO-AVISMA was a major titanium source for Western aerospace primes.",
        "sources": [
            "https://www.reuters.com/business/aerospace-defense/wests-jet-makers-scramble-replace-russian-titanium-2022-03-14/"
        ],
    },
    {
        "id": "ua_neon_2022",
        "name": "Ukraine neon plant shutdown",
        "start": date(2021, 11, 1),
        "peak": date(2022, 2, 24),
        "country": "UA",
        "material": "neon",
        "disruption": DisruptionType.FACTORY_SHUTDOWN,
        "notes": "Ukrainian firms supplied a large share of semiconductor-grade neon.",
        "sources": [
            "https://www.reuters.com/technology/exclusive-ukraine-halts-half-worlds-neon-output-chips-clouding-outlook-2022-03-11/"
        ],
    },
    {
        "id": "ru_pd_2022",
        "name": "Russia palladium and nickel shock",
        "start": date(2021, 11, 1),
        "peak": date(2022, 2, 24),
        "country": "RU",
        "material": "palladium",
        "disruption": DisruptionType.SANCTIONS,
        "notes": "Sanctions and self-sanctioning disrupted PGM and nickel flows.",
        "sources": ["https://www.usgs.gov/centers/national-minerals-information-center"],
    },
    {
        "id": "cn_ga_ge_2023",
        "name": "China gallium and germanium export controls",
        "start": date(2023, 5, 1),
        "peak": date(2023, 8, 1),
        "country": "CN",
        "material": "gallium",
        "disruption": DisruptionType.EXPORT_RESTRICTION,
        "notes": "MOFCOM licensing requirements on gallium and germanium products.",
        "sources": [
            "https://www.csis.org/analysis/chinas-new-export-restrictions-semiconductor-materials"
        ],
    },
    {
        "id": "cn_ge_2023",
        "name": "China germanium export controls",
        "start": date(2023, 5, 1),
        "peak": date(2023, 8, 1),
        "country": "CN",
        "material": "germanium",
        "disruption": DisruptionType.EXPORT_RESTRICTION,
        "notes": "Paired with gallium controls, August 2023.",
        "sources": [
            "https://www.csis.org/analysis/chinas-new-export-restrictions-semiconductor-materials"
        ],
    },
    {
        "id": "redsea_2023",
        "name": "Houthi attacks on Red Sea shipping",
        "start": date(2023, 10, 15),
        "peak": date(2023, 12, 15),
        "country": "YE",
        "material": None,
        "disruption": DisruptionType.SHIPPING_THREAT,
        "notes": "Attacks forced carriers to divert around the Cape of Good Hope.",
        "sources": [
            "https://www.eia.gov/todayinenergy/detail.php?id=61645"
        ],
    },
    {
        "id": "cn_sb_2024",
        "name": "China antimony export controls",
        "start": date(2024, 6, 1),
        "peak": date(2024, 9, 15),
        "country": "CN",
        "material": "antimony",
        "disruption": DisruptionType.EXPORT_RESTRICTION,
        "notes": "Export licensing on antimony and related products.",
        "sources": ["https://www.usgs.gov/centers/national-minerals-information-center"],
    },
    {
        "id": "cn_graphite_2023",
        "name": "China graphite export controls",
        "start": date(2023, 8, 1),
        "peak": date(2023, 12, 1),
        "country": "CN",
        "material": "graphite",
        "disruption": DisruptionType.EXPORT_RESTRICTION,
        "notes": "Graphite licensing followed gallium/germanium controls.",
        "sources": ["https://www.csis.org/analysis"],
    },
    {
        "id": "mm_coup_2021",
        "name": "Myanmar coup and rare earth disruption",
        "start": date(2020, 12, 1),
        "peak": date(2021, 2, 1),
        "country": "MM",
        "material": "rare_earths",
        "disruption": DisruptionType.CIVIL_UNREST,
        "notes": "Coup and subsequent conflict affected Kachin rare earth mining.",
        "sources": ["https://acleddata.com/"],
    },
    {
        "id": "cn_re_threat_2019",
        "name": "China rare earth threats during US trade war (near miss)",
        "start": date(2019, 4, 1),
        "peak": date(2019, 5, 21),
        "country": "CN",
        "material": "rare_earths",
        "disruption": None,  # near miss — precursors without a cutoff
        "notes": "Xi visited a rare earth magnet plant; no full export ban followed.",
        "sources": [
            "https://www.reuters.com/article/us-usa-trade-china-rareearths-idUSKCN1SS23B"
        ],
    },
]


def outcomes_from_episodes() -> list[Outcome]:
    out: list[Outcome] = []
    for ep in EPISODES:
        if ep["disruption"] is None:
            continue
        out.append(
            Outcome(
                occurred_on=ep["peak"],
                country=ep["country"],
                material=ep["material"],
                disruption_type=ep["disruption"],
                name=ep["name"],
                notes=ep["notes"],
            )
        )
    return out


def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)
