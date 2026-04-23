"""OpenFlights airport data loader and search."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "airports.dat"


@dataclass
class Airport:
    iata: str
    name: str
    city: str
    country: str
    lat: float
    lng: float

    def to_dict(self) -> dict:
        return {
            "iata": self.iata,
            "name": self.name,
            "city": self.city,
            "country": self.country,
            "lat": self.lat,
            "lng": self.lng,
        }


_airports: list[Airport] = []
_by_iata: dict[str, Airport] = {}


def load() -> None:
    """Parse airports.dat into memory. Safe to call multiple times."""
    if _airports:
        return
    with DATA_FILE.open(newline="", encoding="utf-8") as f:
        # OpenFlights format: id, name, city, country, IATA, ICAO, lat, lng, ...
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue
            iata = row[4].strip().strip('"')
            if not iata or iata == "\\N" or len(iata) != 3:
                continue
            try:
                lat = float(row[6])
                lng = float(row[7])
            except ValueError:
                continue
            airport = Airport(
                iata=iata.upper(),
                name=row[1].strip().strip('"'),
                city=row[2].strip().strip('"'),
                country=row[3].strip().strip('"'),
                lat=lat,
                lng=lng,
            )
            _airports.append(airport)
            _by_iata[airport.iata] = airport


def get(iata: str) -> Airport | None:
    if not _airports:
        load()
    return _by_iata.get(iata.upper())


def search(q: str, limit: int = 10) -> list[Airport]:
    """Rank: exact IATA > city prefix > city contains > name contains."""
    if not _airports:
        load()
    if not q:
        return []
    needle = q.strip().lower()
    if not needle:
        return []

    exact_iata: list[Airport] = []
    city_prefix: list[Airport] = []
    city_contains: list[Airport] = []
    name_contains: list[Airport] = []
    seen: set[str] = set()

    for a in _airports:
        if a.iata in seen:
            continue
        iata_l = a.iata.lower()
        city_l = a.city.lower()
        name_l = a.name.lower()
        if iata_l == needle:
            exact_iata.append(a)
            seen.add(a.iata)
        elif city_l.startswith(needle) or iata_l.startswith(needle):
            city_prefix.append(a)
            seen.add(a.iata)
        elif needle in city_l:
            city_contains.append(a)
            seen.add(a.iata)
        elif needle in name_l:
            name_contains.append(a)
            seen.add(a.iata)

    combined = exact_iata + city_prefix + city_contains + name_contains
    return combined[:limit]
