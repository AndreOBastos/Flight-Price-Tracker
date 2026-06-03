"""Google Flights fetcher + parser.

We bypass fast-flights' parser because we need layover airports — which are in
the aria-label attributes of each result row but not extracted by fast-flights.
We still reuse fast-flights' TFS filter encoding to build the URL.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass

from fast_flights.filter import TFSData
from fast_flights.flights_impl import FlightData, Passengers
from selectolax.lexbor import LexborHTMLParser
from playwright.async_api import async_playwright, Browser, Playwright

from . import airports


@dataclass
class Leg:
    airline: str
    price: float               # in selected currency units
    currency: str
    dep_iata: str
    dep_time: str              # "5:55 AM on Wed, May 13" (free text from Google)
    arr_iata: str
    arr_time: str
    duration_min: int
    stops: int
    layover_iatas: list[str]   # resolved IATA for each layover, in order
    layover_names: list[str]   # human-readable "Zurich Airport" etc.
    layover_durations_min: list[int]

    def to_dict(self) -> dict:
        def coords_for(iata: str):
            a = airports.get(iata)
            return {"lat": a.lat, "lng": a.lng} if a else None

        route = [self.dep_iata] + self.layover_iatas + [self.arr_iata]
        return {
            "airline": self.airline,
            "price": self.price,
            "currency": self.currency,
            "dep_iata": self.dep_iata,
            "dep_time": self.dep_time,
            "arr_iata": self.arr_iata,
            "arr_time": self.arr_time,
            "duration_min": self.duration_min,
            "stops": self.stops,
            "layovers": [
                {"iata": iata, "name": name, "duration_min": dur}
                for iata, name, dur in zip(
                    self.layover_iatas, self.layover_names, self.layover_durations_min
                )
            ],
            "route_iatas": route,
            "route_coords": [coords_for(i) for i in route],
        }


# --- Name → IATA resolver -----------------------------------------------------

_name_to_iata_cache: dict[str, str | None] = {}


_PUNCT_RE = re.compile(r"[\u2010-\u2015\u2212\-/,.()\[\]'\"]")


def _norm(s: str) -> str:
    """Lowercase + strip diacritics + replace punctuation (dashes, slashes, etc.) with space."""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_ = "".join(c for c in nfkd if not unicodedata.combining(c))
    spaced = _PUNCT_RE.sub(" ", ascii_)
    return " ".join(spaced.split()).lower().strip()


_STOPWORDS = {
    "aeroporto", "aeropuerto", "aeroport", "flughafen", "airport",
    "lufthavn", "havn", "international", "intl", "regional",
    "de", "del", "do", "da",
}


def _simplify(norm_name: str) -> str:
    tokens = [t for t in norm_name.split() if t not in _STOPWORDS]
    return " ".join(tokens).strip()


def _airport_name_to_iata(name: str) -> str | None:
    """Best-effort map a human airport name (e.g. 'Zurich Airport') to IATA.

    Uses word-level matching (not substring) to avoid false hits like
    'Gove' matching 'Governor'.
    """
    key = _norm(name)
    if key in _name_to_iata_cache:
        return _name_to_iata_cache[key]

    airports.load()
    key_simpl = _simplify(key)
    key_tokens = set(key_simpl.split())

    # 1. Exact full-name match.
    for a in airports._airports:
        if _norm(a.name) == key:
            _name_to_iata_cache[key] = a.iata
            return a.iata

    # 2. Exact simplified-name match.
    for a in airports._airports:
        if _simplify(_norm(a.name)) == key_simpl:
            _name_to_iata_cache[key] = a.iata
            return a.iata

    # 3. Exact city match.
    for a in airports._airports:
        if _norm(a.city) == key:
            _name_to_iata_cache[key] = a.iata
            return a.iata

    # 4. Token-overlap with word boundaries. Accept when:
    #      (a) query tokens ⊆ candidate tokens, or
    #      (b) candidate tokens ⊆ query tokens, or
    #      (c) at least 3 shared tokens (fuzzy match for long names).
    best: Airport | None = None
    best_score = 0
    for a in airports._airports:
        a_tokens = set(_simplify(_norm(a.name)).split())
        if not a_tokens:
            continue
        shared = a_tokens & key_tokens
        if not shared:
            continue
        q_subset = key_tokens and key_tokens.issubset(a_tokens)
        a_subset = a_tokens.issubset(key_tokens)
        if q_subset or a_subset or len(shared) >= 3:
            # Score favors more shared tokens; bonus if the candidate's
            # CITY appears in the query (disambiguates FRA vs QEF for "Frankfurt Airport").
            city_tokens = set(_simplify(_norm(a.city)).split())
            city_bonus = 500 if city_tokens and city_tokens.issubset(key_tokens) else 0
            score = len(shared) * 100 + city_bonus - (len(a_tokens) - len(shared))
            if score > best_score:
                best_score = score
                best = a

    result = best.iata if best else None
    _name_to_iata_cache[key] = result
    return result


# --- Parsing ------------------------------------------------------------------

# aria-label patterns (Google Flights). Keep them loose — Google tweaks wording.
_RX_SUMMARY = re.compile(
    r"From\s+([\d,]+)\s+(.+?)(?:\s+(?:round trip total|one[- ]way))?\.\s*"
    r"(Nonstop|\d+\s+stops?)\s+flight\s+with\s+(.+?)\."
    r"\s*Leaves\s+(.+?)\s+at\s+(.+?)\s+and\s+arrives\s+at\s+(.+?)\s+at\s+(.+?)\.\s*"
    r"Total\s+duration\s+([\d hrmin]+?)\.",
    re.IGNORECASE | re.DOTALL,
)
_RX_LAYOVER = re.compile(
    r"Layover\s+\(\d+\s+of\s+\d+\)\s+is\s+(?:a|an)\s+(\d+(?:\s+hr)?(?:\s+\d+)?(?:\s+min)?)"
    r"(?:\s+overnight)?\s+layover\s+at\s+([^\.]+?)(?:\s+in\s+[^\.]+)?\.",
    re.IGNORECASE,
)
_RX_DUR = re.compile(r"(?:(\d+)\s*hr)?\s*(?:(\d+)\s*min)?", re.IGNORECASE)


def _parse_duration(s: str) -> int:
    m = _RX_DUR.search(s or "")
    if not m:
        return 0
    h, mm = m.groups()
    return (int(h) if h else 0) * 60 + (int(mm) if mm else 0)


def _parse_price(raw_number: str, raw_currency_text: str, fallback_currency: str) -> tuple[float, str]:
    """`raw_number` is like '686' or '1,240'. `raw_currency_text` is like
    'US dollars' or 'Brazilian reais'. We keep the raw number; currency label is
    whatever the user requested (we pass `curr=` to Google)."""
    n = float(raw_number.replace(",", ""))
    return n, fallback_currency


_BLOCK_MARKERS = (
    "unusual traffic",
    "are you a robot",
    "/sorry/index",
    "captcha",
    "before you continue to google",
)
_NO_FLIGHTS_MARKERS = (
    "no flights found",
    "no results found",
    "no flights match",
    "we couldn't find any flights",
    "try changing your search",
    "no nonstop flights",  # weaker, kept for completeness
)


def classify_results(html: str) -> tuple[str, int]:
    """Return (reason, row_count) for a Google Flights results page.

    reason ∈ {"ok", "blocked", "no_schedule", "no_flights"}
      - ok            → at least one flight row in the DOM
      - blocked       → CAPTCHA / "unusual traffic" / Google sorry page
      - no_flights    → page has a "no flights" / "no results" message
      - no_schedule   → page rendered but has no row and no explanatory text
                        (Google's empty stub for routes/dates with no published
                        schedule data, e.g. small origins far in the future)

    Uses DOM/text content — not byte size — to decide.
    """
    if not html or not html.strip():
        return "no_schedule", 0

    parser = LexborHTMLParser(html)
    rows = parser.css("li.pIav2d")
    if rows:
        return "ok", len(rows)

    # Use rendered text (not raw HTML) so we don't false-match on script/style.
    body_node = parser.css_first("body") or parser.css_first("[role='main']")
    text = (body_node.text(separator=" ") if body_node else "").lower()

    if any(m in text for m in _BLOCK_MARKERS):
        return "blocked", 0
    if any(m in text for m in _NO_FLIGHTS_MARKERS):
        return "no_flights", 0
    return "no_schedule", 0


def parse_legs(
    html: str,
    dep_iata: str,
    arr_iata: str,
    currency: str,
) -> list[Leg]:
    """Parse Google Flights one-way or round-trip results HTML into Legs.

    Each flight card has:
      - A summary aria-label on an outer element (From X. N stop flight with ...)
      - Zero or more nested "Layover (..)" aria-labels.
    """
    parser = LexborHTMLParser(html)
    legs: list[Leg] = []
    seen_summaries: set[str] = set()

    # Each flight result row is a <li class="pIav2d"> in Google Flights.
    for row in parser.css("li.pIav2d"):
        summary_label = None
        for node in row.css("[aria-label]"):
            label = node.attributes.get("aria-label") or ""
            if _RX_SUMMARY.search(label):
                summary_label = label
                break
        if not summary_label:
            continue
        m = _RX_SUMMARY.search(summary_label)
        if not m:
            continue
        if summary_label in seen_summaries:
            continue
        seen_summaries.add(summary_label)

        price_num, currency_text, stops_txt, airline, dep_airport_name, dep_time, arr_airport_name, arr_time, duration_text = m.groups()
        price_val, cur = _parse_price(price_num, currency_text, currency)
        duration_min = _parse_duration(duration_text)
        stops = 0 if "nonstop" in stops_txt.lower() else int(re.search(r"\d+", stops_txt).group())

        layover_names: list[str] = []
        layover_durations: list[int] = []
        for inner in row.css("[aria-label]"):
            label_text = inner.attributes.get("aria-label") or ""
            for lm in _RX_LAYOVER.finditer(label_text):
                lay_dur_txt, lay_name = lm.groups()
                layover_durations.append(_parse_duration(lay_dur_txt))
                layover_names.append(lay_name.strip())

        # Dedup while preserving order
        seen = set()
        lay_names_dedup, lay_durs_dedup = [], []
        for n, d in zip(layover_names, layover_durations):
            key = (n, d)
            if key in seen:
                continue
            seen.add(key)
            lay_names_dedup.append(n)
            lay_durs_dedup.append(d)

        layover_iatas = [_airport_name_to_iata(n) or "???" for n in lay_names_dedup]

        legs.append(
            Leg(
                airline=airline.strip(),
                price=price_val,
                currency=cur,
                dep_iata=dep_iata,
                dep_time=dep_time.strip(),
                arr_iata=arr_iata,
                arr_time=arr_time.strip(),
                duration_min=duration_min,
                stops=stops,
                layover_iatas=layover_iatas,
                layover_names=lay_names_dedup,
                layover_durations_min=lay_durs_dedup,
            )
        )

    return legs


# --- Fetcher with persistent browser -----------------------------------------


_THROTTLE_DELAY = 1.5      # baseline seconds between sequential fetches
_THROTTLE_MAX_DELAY = 20   # cap for exponential backoff on consecutive blocks

log = logging.getLogger(__name__)


class GoogleFlightsFetcher:
    """Maintains a single Playwright browser. Serialises page fetches to avoid
    Google bot-detection from concurrent requests.

    Tracks consecutive "throttle" responses (suspiciously tiny HTML payloads)
    and applies exponential backoff + browser restart to recover.
    """

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()
        self._consecutive_throttles = 0

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

    async def _restart_browser(self) -> None:
        """Close and re-launch the browser to drop cookies/fingerprint state."""
        log.warning("Restarting Playwright browser to clear throttle state…")
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:
            pass
        self._browser = None
        if self._pw is None:
            self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)

    async def _fetch_html(self, url: str) -> str:
        """Fetch a single Google Flights URL. Must be called while holding _lock.

        We try to wait for flight rows, but if the wait times out (no results
        found, different layout, bot check), we still return whatever HTML we
        can grab — the parser handles empty/malformed content by returning
        no legs, and the caller retries or reports "no round trip".
        """
        assert self._browser is not None
        context = await self._browser.new_context()
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            # Handle EU consent screen.
            if page.url.startswith("https://consent.google.com"):
                try:
                    await page.click('text="Accept all"', timeout=5_000)
                    await page.wait_for_load_state("domcontentloaded", timeout=10_000)
                except Exception:
                    pass
            # Wait for flight rows OR a "no flights found" indicator — whichever
            # appears first. If neither appears within the timeout, we proceed
            # with whatever HTML we have.
            try:
                await page.wait_for_selector(
                    ".eQ35Ce, li.pIav2d, text=/no.*(flights|results).*found/i",
                    timeout=20_000,
                )
            except Exception:
                pass
            try:
                body = await page.evaluate(
                    "() => document.querySelector('[role=\"main\"]')?.innerHTML || document.body.innerHTML"
                )
            except Exception:
                body = ""
        finally:
            await context.close()
        return body

    def _build_url(self, dep_iata: str, arr_iata: str, date_str: str, currency: str) -> str:
        filter_ = TFSData.from_interface(
            flight_data=[FlightData(date=date_str, from_airport=dep_iata, to_airport=arr_iata)],
            trip="one-way",
            passengers=Passengers(adults=1),
            seat="economy",
            max_stops=None,
        )
        params = {
            "tfs": filter_.as_b64().decode(),
            "hl": "en",
            "tfu": "EgQIABABIgA",
            "curr": currency,
        }
        return "https://www.google.com/travel/flights?" + "&".join(f"{k}={v}" for k, v in params.items())

    async def fetch_oneway_html(
        self,
        *,
        dep_iata: str,
        arr_iata: str,
        date_str: str,
        currency: str,
    ) -> str:
        url = self._build_url(dep_iata, arr_iata, date_str, currency)
        # Serialise ALL fetches through one lock to avoid concurrent requests
        # that trigger Google's bot detection.
        async with self._lock:
            if self._browser is None:
                await self.start()
            html = await self._fetch_html(url)
            # Adaptive cooldown: classify the actual page content. Block pages
            # earn an exponential backoff; everything else (results, no-results,
            # no-schedule stubs) gets the baseline pause.
            reason, _ = classify_results(html)
            if reason == "blocked":
                self._consecutive_throttles += 1
                cooldown = min(
                    _THROTTLE_DELAY * (2 ** self._consecutive_throttles),
                    _THROTTLE_MAX_DELAY,
                )
                log.warning(
                    "Bot-detection page for %s→%s on %s (consecutive=%d). "
                    "Cooling down %.1fs.",
                    dep_iata, arr_iata, date_str,
                    self._consecutive_throttles, cooldown,
                )
                await asyncio.sleep(cooldown)
            else:
                self._consecutive_throttles = 0
                await asyncio.sleep(_THROTTLE_DELAY)
        return html

    async def top_oneways(
        self,
        *,
        dep_iata: str,
        arr_iata: str,
        date_str: str,
        limit: int = 5,
        retries: int = 2,
    ) -> tuple[list[Leg], str]:
        """Return (legs, reason).

        `reason` describes the outcome:
          - "ok"           → got `legs`, cheapest first.
          - "no_schedule"  → Google has no schedule data for this route+date
                             (typical for small origins far out, or routes
                             where airlines haven't published fares yet).
          - "blocked"      → Google served a bot-detection page even after
                             retries — likely temporarily blocked.
          - "no_flights"   → Full results page with no itineraries.
        """
        for attempt in range(1, retries + 2):
            html = await self.fetch_oneway_html(
                dep_iata=dep_iata,
                arr_iata=arr_iata,
                date_str=date_str,
                currency="USD",
            )
            reason, row_count = classify_results(html)
            if reason == "ok":
                legs = parse_legs(html, dep_iata=dep_iata, arr_iata=arr_iata, currency="USD")
                if legs:
                    legs.sort(key=lambda leg: leg.price)
                    return legs[:limit], "ok"
                # DOM had rows but the parser couldn't extract — treat as
                # transient and retry once; otherwise surface as no_flights.
                log.warning(
                    "DOM had %d row(s) but parser extracted nothing for %s→%s on %s",
                    row_count, dep_iata, arr_iata, date_str,
                )
                if attempt > retries:
                    return [], "no_flights"
                continue

            if reason == "blocked":
                if attempt <= retries:
                    log.warning(
                        "Blocked page for %s→%s on %s (attempt %d/%d), restarting browser…",
                        dep_iata, arr_iata, date_str, attempt, retries + 1,
                    )
                    async with self._lock:
                        await self._restart_browser()
                        self._consecutive_throttles = 0
                    continue
                return [], "blocked"

            # "no_schedule" or "no_flights": Google's answer is stable, so we
            # don't retry — that would just waste time.
            log.info(
                "%s for %s→%s on %s.", reason, dep_iata, arr_iata, date_str,
            )
            return [], reason
        return [], "blocked"


fetcher = GoogleFlightsFetcher()
