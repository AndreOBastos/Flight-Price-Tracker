"""In-memory search job manager + SSE event queues.

For each date in the range, we do two one-way searches (outbound + return) in
parallel, returning the top 5 cheapest combos. Prices are fetched in USD then
converted to the user's selected currency.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import product

from currency_converter import CurrencyConverter

from . import amenities, gflights

log = logging.getLogger(__name__)
_cc = CurrencyConverter()

TOP_N = 5  # number of cheapest round-trip combos to return per day


@dataclass
class Params:
    origin: str
    dest: str
    trip_days: int
    date_from: date
    date_to: date
    currency: str


@dataclass
class Job:
    id: str
    params: Params
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    done: bool = False


_jobs: dict[str, Job] = {}


def _dates(params: Params) -> list[date]:
    out: list[date] = []
    d = params.date_from
    while d <= params.date_to:
        out.append(d)
        d += timedelta(days=1)
    return out


def _convert(amount_usd: float, target: str) -> float:
    """Convert USD amount to target currency. Falls back to 1:1 if unknown."""
    if target == "USD":
        return amount_usd
    try:
        return round(_cc.convert(amount_usd, "USD", target), 2)
    except Exception:
        return amount_usd


def _convert_leg(leg_dict: dict, target: str) -> dict:
    """Convert a single leg dict's price from USD to target currency."""
    return {**leg_dict, "price": _convert(leg_dict["price"], target), "currency": target}


async def _sweep_one_date(job: Job, departure: date) -> dict:
    params = job.params
    ret = departure + timedelta(days=params.trip_days)

    # Run outbound then inbound sequentially — the fetcher serialises requests
    # through a single Playwright browser to avoid Google throttling.
    outbound_legs, out_reason = await gflights.fetcher.top_oneways(
        dep_iata=params.origin,
        arr_iata=params.dest,
        date_str=departure.isoformat(),
        limit=TOP_N,
    )
    inbound_legs, in_reason = await gflights.fetcher.top_oneways(
        dep_iata=params.dest,
        arr_iata=params.origin,
        date_str=ret.isoformat(),
        limit=TOP_N,
    )

    if not outbound_legs or not inbound_legs:
        # Prefer the more specific failure mode if they differ.
        priority = ("blocked", "no_schedule", "no_flights", "ok")
        empty = [r for r, legs in [(out_reason, outbound_legs), (in_reason, inbound_legs)] if not legs]
        reason = min(empty, key=lambda r: priority.index(r) if r in priority else 99)
        return {
            "departure_date": departure.isoformat(),
            "return_date": ret.isoformat(),
            "options": [],
            "reason": reason,
        }

    # Build all combos, rank by total price, take top N.
    combos = []
    for out_leg, in_leg in product(outbound_legs, inbound_legs):
        combos.append((out_leg.price + in_leg.price, out_leg, in_leg))
    combos.sort(key=lambda c: c[0])
    combos = combos[:TOP_N]

    cur = params.currency
    options = []
    for total_usd, out_leg, in_leg in combos:
        airline_codes: list[str] = []
        for leg in (out_leg, in_leg):
            code = _short_airline_code(leg.airline)
            if code and code not in airline_codes:
                airline_codes.append(code)
        options.append({
            "total_price": _convert(total_usd, cur),
            "currency": cur,
            "outbound": _convert_leg(out_leg.to_dict(), cur),
            "inbound": _convert_leg(in_leg.to_dict(), cur),
            "amenity_hints": amenities.for_flight(airline_codes),
        })

    return {
        "departure_date": departure.isoformat(),
        "return_date": ret.isoformat(),
        "options": options,
    }


# Rough airline-name → IATA-code hints for the amenities lookup.
_AIRLINE_NAME_HINTS = {
    "american airlines": "AA",
    "american": "AA",
    "delta": "DL",
    "united": "UA",
    "jetblue": "B6",
    "alaska": "AS",
    "southwest": "WN",
    "frontier": "F9",
    "spirit": "NK",
    "lufthansa": "LH",
    "british airways": "BA",
    "air france": "AF",
    "klm": "KL",
    "iberia": "IB",
    "tap air portugal": "TP",
    "tap portugal": "TP",
    "swiss": "LX",
    "ryanair": "FR",
    "easyjet": "U2",
    "emirates": "EK",
    "qatar airways": "QR",
    "qatar": "QR",
    "turkish airlines": "TK",
    "turkish": "TK",
    "air canada": "AC",
    "japan airlines": "JL",
    "ana": "NH",
    "all nippon airways": "NH",
    "singapore airlines": "SQ",
    "cathay pacific": "CX",
    "qantas": "QF",
    "virgin atlantic": "VS",
    "ita airways": "AZ",
    "gol": "G3",
    "latam": "LA",
    "azul": "AD",
    "aer lingus": "EI",
    "azores airlines": "S4",
    "icelandair": "FI",
    "finnair": "AY",
    "scandinavian airlines": "SK",
    "sas": "SK",
    "vueling": "VY",
    "wizz air": "W6",
    "norwegian": "DY",
    "play": "OG",
    "klm royal dutch airlines": "KL",
}


def _short_airline_code(name: str) -> str:
    return _AIRLINE_NAME_HINTS.get(name.lower().strip(), name[:2].upper())


async def _run(job: Job) -> None:
    dates = _dates(job.params)
    total = len(dates)
    for idx, d in enumerate(dates, start=1):
        try:
            payload = await _sweep_one_date(job, d)
            await job.queue.put({
                "type": "result",
                "progress": {"done": idx, "total": total, "current_date": d.isoformat()},
                **payload,
            })
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.exception("sweep failed for %s", d)
            await job.queue.put({
                "type": "error",
                "progress": {"done": idx, "total": total, "current_date": d.isoformat()},
                "departure_date": d.isoformat(),
                "message": f"{type(e).__name__}: {e}",
            })
    await job.queue.put({"type": "done", "total": total})
    job.done = True


def start(params: Params) -> Job:
    job = Job(id=str(uuid.uuid4()), params=params)
    _jobs[job.id] = job
    job.task = asyncio.create_task(_run(job))
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


async def stream(job: Job):
    """Yield SSE-formatted event strings from the job queue."""
    while True:
        event = await job.queue.get()
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("type") == "done":
            break
    _jobs.pop(job.id, None)
