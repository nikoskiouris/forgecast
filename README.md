# Gridpulse

**Calibrated map of the AI power buildout.**

Dark US map. Where load, permits, and giga-sites land next — then the mechanical ticker book that sits underneath (utilities, IPPs, REITs, grid equipment, regional banks).

Publisher, not an adviser.

> There is a 90% probability that ERCOT West weekly peak load grows ≥8% YoY within 180 days. Exposed: VST, NRG. Analog: ERCOT-West 2025 breakout.

Demo date: **2026-06-01**.

## Quick start

Python 3.10+ and Node 20+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cd web && npm install && npm run build && cd ..
forgecast serve     # http://127.0.0.1:8000
forgecast forecast
forgecast snapshot  # bake docs/ for GitHub Pages
```

One process locally: `forgecast serve`.

## Signals

| Family | Question |
| --- | --- |
| `load_growth` | BA weekly peak ≥8% YoY (EIA-930) |
| `permit_mw` | County permit-MW crosses the giga-site bar |
| `giga_site` | Named campus announcement within 90 days |

GDELT is attention only. It never becomes a label.

## API

- `GET /` map
- `GET /api/health`
- `GET /api/meta`
- `GET /api/forecast`
- `GET /api/map`
- `GET /api/hex/{3|4|5}`
- `GET /api/cell/{geo_id}`
- `GET /api/flows`
- `GET /api/events`
- `GET /api/report`
- `GET /api/backtest`

The SPA tries `/api/...` then falls back to baked `data/*.json` so GitHub Pages works with no server.

## License

MIT
