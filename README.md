# Forgecast

**Know what will affect your day—before it does.**

You type in home, work, the gym. Forgecast reads live Atlanta road closures, city permits, MARTA alerts, weather, and airport delays — then tells you only what could hit **you**.

The map is evidence. The product is the briefing.

> Leave 15 minutes earlier: lane closures affect your usual route to work.
> Avoid Midtown after 5:30 PM: a major event is expected to create heavy traffic.
> MARTA Red Line delays may affect your backup route.

Atlanta metro only.

## Quick start

Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

forgecast serve     # http://127.0.0.1:8000
forgecast day --home "Ponce City Market" --work "Georgia Tech"
forgecast snapshot  # bake live events into docs/ for GitHub Pages
```

First screen:

**What could disrupt your day?**  
Enter a home, work, or other location. Forgecast monitors what’s happening nearby and tells you what matters.

## Live sources (no dummy events)

| Feed | What it is |
| --- | --- |
| GDOT / 511 | Metro traffic interruptions, construction, races, filming, major events |
| Atlanta DOT | Lane / street closure permits |
| Atlanta Public Works | Utility work with lane or road closures |
| NWS | Active alerts that hit metro counties |
| Open-Meteo | Hourly rain / storm windows |
| MARTA OTP | Rail, streetcar, and bus service alerts |
| FAA NAS Status | Hartsfield-Jackson (ATL) delays |

If a feed is down, the others still publish. Nothing is invented to fill the gap.

## How it works

```
Your places (and commute)
        ↓
Live Atlanta events with coordinates
        ↓
Distance to home / work / gym / route
        ↓
Personalized briefing + map pins
```

Places stay in the browser. One process locally: `forgecast serve`.

## API

- `GET /` map + briefing UI
- `GET /api/events` live city events
- `GET /api/day?home=...&work=...&gym=...`
- `POST /api/day` `{ "places": [{ "label": "home", "address": "..." }] }`
- `GET /api/geocode?q=...`

## License

MIT
