"""Pydantic request/response models."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


ALLOWED_CURRENCIES = [
    "USD", "EUR", "GBP", "BRL", "CAD", "AUD", "JPY", "CHF", "MXN", "INR"
]


class SearchRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    dest: str = Field(..., min_length=3, max_length=3)
    trip_days: int = Field(..., ge=0, le=60)
    date_from: date
    date_to: date
    currency: str = "USD"

    @field_validator("origin", "dest")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

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
