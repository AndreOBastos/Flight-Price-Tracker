"""FastAPI app: airport autocomplete, search start, SSE event stream."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import airports, amenities, gflights, search_manager
from .models import SearchRequest, SearchStartResponse, ALLOWED_CURRENCIES

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    airports.load()
    amenities.load()
    await gflights.fetcher.start()
    yield
    await gflights.fetcher.stop()


app = FastAPI(lifespan=lifespan, title="Air Ticket Price Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/airports")
def airports_search(q: str = Query("", max_length=80), limit: int = 10):
    return [a.to_dict() for a in airports.search(q, limit=limit)]


@app.get("/api/currencies")
def list_currencies():
    return ALLOWED_CURRENCIES


@app.post("/api/search", response_model=SearchStartResponse)
async def start_search(req: SearchRequest):
    if req.date_to < req.date_from:
        raise HTTPException(400, "date_to must be >= date_from")
    if (req.date_to - req.date_from).days > 60:
        raise HTTPException(400, "date range must be <= 60 days")
    if not airports.get(req.origin):
        raise HTTPException(400, f"unknown origin IATA: {req.origin}")
    if not airports.get(req.dest):
        raise HTTPException(400, f"unknown destination IATA: {req.dest}")

    params = search_manager.Params(
        origin=req.origin,
        dest=req.dest,
        trip_days=req.trip_days,
        date_from=req.date_from,
        date_to=req.date_to,
        currency=req.currency,
    )
    job = search_manager.start(params)
    total = (req.date_to - req.date_from).days + 1
    return SearchStartResponse(search_id=job.id, total_dates=total)


@app.get("/api/search/{job_id}/events")
async def search_events(job_id: str):
    job = search_manager.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return StreamingResponse(
        search_manager.stream(job),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# Serve the built frontend in production.
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
