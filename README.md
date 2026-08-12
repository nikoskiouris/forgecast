# Forgecast

Calibrated **probabilities** of disruption to the U.S. and allied defense industrial base — not declarations that something will happen.

A defense manufacturer can ask:

> What foreign events are most likely to disrupt our supply chain during the next 180 days?

Forgecast answers in this shape:

> There is a 31% probability of new export restrictions affecting titanium (Russia) within 180 days, up from 22% last month. Three weapons programs and one supplier are exposed. The probability moved because of these developments.

Then it shows the indicators, historical analogs, how today differs, what would raise or lower the probability, and the sources.

This is a scoped prototype. The wedge is **medium-horizon, calibrated forecasting tied to a customer’s actual assets and suppliers** — not another breaking-news alerting product.

## What it forecasts

- Export restrictions on strategic materials
- Port or border closures
- Sanctions
- Coups and major civil unrest
- Conflict escalation
- Factory shutdowns
- Threats to shipping routes
- Government nationalization or seizure of assets

## How it works

```
Global news and public data
        ↓
Structured event timeline
        ↓
Historical pattern retrieval
        ↓
Statistical forecasting models
        ↓
Probability, evidence, and analogs
```

1. **Read and structure the world.** Events are stored as `actor → action → target → material → date`. Live ingest uses [GDELT](https://www.gdeltproject.org/) (CAMEO-coded global events). The demo ships with a historically-inspired sample world covering 2009–2025 (rare earths 2010, Suez 2021, Russia/Ukraine 2022, China gallium/germanium/graphite/antimony controls, Red Sea 2023–24, Myanmar 2021, plus a 2019 rare-earth near miss).
2. **Temporal knowledge graph.** Each event becomes a dated edge: sanctions, force posture, trade rhetoric, material mentions.
3. **Historical analogs.** Cosine similarity over 120-day event-mix windows, anchored to named episodes. Similarity is **one input**, not the algorithm. The write-up always states how today differs (especially economic interdependence).
4. **Calibrated ensemble.** Base rate + time-series logistic + discrete-time hazard + sequence mix + analog outcome rate, then isotonic calibration. The LLM-shaped prose is a template over those numbers. It does not invent the probability.

## Quick start

Python 3.10+.

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

forgecast forecast
forgecast report
forgecast backtest
forgecast serve     # http://127.0.0.1:8000
```

Default `as_of` is **2024-06-01** so the sample world still has a future (China antimony controls land later that year). Pass `--as-of` to change it.

```bash
forgecast seed
forgecast ingest --start 2024-06-01 --end 2024-06-07   # live GDELT
forgecast graph
```

Demo portfolio: [`data/portfolios/demo_defense.yaml`](data/portfolios/demo_defense.yaml) (F-35, Virginia-class, Patriot, GMLRS, SATCOM and their material/supplier graph).

## Backtesting

The hard part is not reading articles. It is proving the forecasts work.

`forgecast backtest` walks forward in time:

- Train only on labels that would already have been known (`as_of + 180 days` before the test year)
- Score with Brier and log loss against a base-rate baseline
- Print a reliability table

On the sample world the ensemble should beat a constant base-rate forecast (positive Brier skill). That is a pipeline test, not a claim about live geopolitical accuracy.

A serious evaluation still needs:

- Real GDELT/ACLED history with as-of cutoffs
- Independently dated outcome labels (not reconstructed from the same news)
- Comparison to professional forecasters
- Published misses, not only hits

## What is real vs. not yet

| Piece | Status |
| --- | --- |
| Event schema, SQLite graph, analog retrieval | Working |
| Ensemble + walk-forward Brier/log loss | Working on sample world |
| Portfolio exposure (programs / suppliers) | Working |
| Evidence write-up (drivers, analogs, deltas, sources) | Working (templates) |
| GDELT ingest | Working (network) |
| ACLED | Not wired (needs a key) |
| LLM article → event extraction | Not wired; GDELT CAMEO + keywords stand in |
| Temporal graph neural net | Not in v0; features are tabular |
| Live production calibration | Not claimed |

## API

- `GET /` dashboard
- `GET /api/forecast?as_of=2024-06-01&horizon=180`
- `GET /api/report?rank=1`

## Why this wedge

Generic “AI that predicts world events” is too broad to score. Defense-industrial supply disruption is valuable, measurable, and dual-use: primes, logistics commands, insurers, shippers, commodity desks.

Detection companies (Dataminr, Primer) already cover breaking news. Forgecast is the 30–180 day probability layer sitting on top of a customer’s bill of materials.

## License

MIT
