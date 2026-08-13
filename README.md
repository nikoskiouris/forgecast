# Forgecast

**Know what will affect your day—before it does.**

Not a fastest-route app. You type home and work. Forgecast names the Atlanta corridors you actually choose — **I-85 vs I-285** — then stacks live city events by whether they will punch **your** day.

The map is evidence. The product is which of your habits is in trouble.

> Your usual I-285 is in trouble. I-85 is the clean corridor today.
>
> Hits your day: crash on I-285 at Memorial.
> Could hit you: lane closure on I-85, if you switch.

Atlanta metro only.

## Quick start

Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

forgecast serve     # http://127.0.0.1:8000
forgecast day --home "2855 Briarlake Road" --work "5200 Buffington Road"
forgecast snapshot  # bake live events into docs/ for GitHub Pages
```

First screen:

**What could disrupt your day?**  
Home and work. Forgecast names your corridors and ranks what will actually hit you.

Tap the corridor you actually drive. That becomes your usual. The stack reorders.

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
Your places
        ↓
Named corridors (I-85, I-285, …) — not one GPS polyline
        ↓
Live Atlanta events with coordinates
        ↓
Hits your day / could hit you / later this week
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
