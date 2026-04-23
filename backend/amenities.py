"""Hand-curated airline amenity hints. Labeled as 'typical' not guaranteed."""
from __future__ import annotations

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "airline_amenities.json"

_data: dict[str, dict] = {}


def load() -> None:
    global _data
    if _data:
        return
    with DATA_FILE.open(encoding="utf-8") as f:
        _data = json.load(f)


def for_flight(airline_codes: list[str]) -> dict:
    """Merge hints across carriers in the itinerary.

    If multiple carriers disagree, we show each carrier's hint. If a carrier is
    unknown, its fields become '—'.
    """
    if not _data:
        load()

    hints_by_carrier: dict[str, dict] = {}
    for code in airline_codes:
        code_up = code.upper()
        hints_by_carrier[code_up] = _data.get(code_up) or {
            "name": code_up,
            "wifi": "—",
            "power": "—",
            "legroom": "—",
            "carryon": "—",
            "checked": "—",
        }
    return hints_by_carrier
