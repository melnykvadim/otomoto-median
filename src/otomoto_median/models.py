from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    url: str
    price: int | None
    currency: str | None
    year: int | None
    mileage_km: int | None
    fuel_type: str | None
    gearbox: str | None
    engine_capacity_cc: int | None
    engine_power_hp: int | None
    make: str | None
    model: str | None
    city: str | None
    region: str | None
    seller_type: str | None  # "professional" | "private" | None
    created_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PriceStats:
    n: int
    n_without_price: int
    median: float | None
    mean: float | None
    min: int | None
    max: int | None
    q1: float | None
    q3: float | None
    currency: str
    total_on_otomoto: int | None
    scraped: int
    pages_fetched: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
