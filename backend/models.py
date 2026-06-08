"""Pydantic request/response models."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


ALLOWED_CURRENCIES = [
    "USD", "EUR", "GBP", "BRL", "CAD", "AUD", "JPY", "CHF", "MXN", "INR"
]

MAX_AIRPORTS_PER_SIDE = 4


class SearchRequest(BaseModel):
    # Lists let the user enter multiple airports for cities like NYC (JFK/EWR/LGA)
    # or London (LHR/LGW/STN/LCY).
    origins: list[str] = Field(..., min_length=1, max_length=MAX_AIRPORTS_PER_SIDE)
    dests: list[str] = Field(..., min_length=1, max_length=MAX_AIRPORTS_PER_SIDE)
    trip_days: int = Field(..., ge=0, le=60)
    date_from: date
    date_to: date
    currency: str = "USD"

    @field_validator("origins", "dests")
    @classmethod
    def _norm_iatas(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in v:
            iata = raw.strip().upper()
            if len(iata) != 3 or not iata.isalpha():
                raise ValueError(f"invalid IATA code: {raw!r}")
            if iata in seen:
                continue
            seen.add(iata)
            out.append(iata)
        return out

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_CURRENCIES:
            raise ValueError(f"currency must be one of {ALLOWED_CURRENCIES}")
        return v


class SearchStartResponse(BaseModel):
    search_id: str
    total_dates: int
