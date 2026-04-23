# Air Ticket Price Finder

Sweep a date range for cheap round-trip flights. For each departure date, find
the cheapest round-trip whose return is exactly `trip_days` later. See per-leg
segments, the flight path (including layovers) on a map, and best-effort
carrier amenity hints.

## How it works

- **Sweep:** for each date in the range, we fire two parallel one-way searches
  (outbound and return) against Google Flights via a persistent Playwright
  browser. We parse the results page's `aria-label` attributes — Google exposes
  full layover airport names + durations there.
- **Map:** Leaflet + OpenStreetMap. Airport coords come from the bundled
  OpenFlights `airports.dat`. Routes are drawn as great-circle arcs.
- **Amenities:** a small hand-curated JSON (`backend/data/airline_amenities.json`)
  of typical wi-fi / power / legroom / bag hints per carrier. Labeled as
  "typical for these carriers — not guaranteed."
- **Streaming:** results are pushed to the browser as each date completes via
  Server-Sent Events.

## Setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
playwright install chromium
```

Start the API:

```bash
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Production

```bash
cd frontend && npm run build    # emits frontend/dist
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The FastAPI app serves `frontend/dist/` at `/` when present.

## Known limitations

- Airline names come from Google as free text; unmapped carriers fall back to
  a 2-letter approximation in the amenities panel.
- Layover airports are matched from Google's natural-language names against
  OpenFlights records (normalizing for diacritics); rare airports may show
  as `???` on the map.
- Per-leg pricing is approximate: we sum the cheapest outbound + cheapest
  return at the fare level Google quotes as a one-way.
# Flight-Price-Tracker
