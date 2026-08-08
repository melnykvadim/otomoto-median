from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence

from .models import Listing, PriceStats


def valid_prices(listings: Iterable[Listing]) -> list[int]:
    return sorted(item.price for item in listings if item.price is not None and item.price > 0)


def percentile_nearest_rank(sorted_values: Sequence[float], pct: float) -> float | None:
    """Inclusive nearest-rank percentile for 0 < pct <= 100."""
    if not sorted_values:
        return None
    if pct <= 0:
        return float(sorted_values[0])
    if pct >= 100:
        return float(sorted_values[-1])
    rank = max(1, int(round(pct / 100 * len(sorted_values))))
    return float(sorted_values[rank - 1])


def compute_stats(
    listings: Sequence[Listing],
    *,
    total_on_otomoto: int | None = None,
    pages_fetched: int = 0,
    truncated: bool = False,
    currency: str = "PLN",
) -> PriceStats:
    prices = valid_prices(listings)
    n_without = sum(1 for item in listings if item.price is None or item.price <= 0)
    if not prices:
        return PriceStats(
            n=0,
            n_without_price=n_without,
            median=None,
            mean=None,
            min=None,
            max=None,
            q1=None,
            q3=None,
            currency=currency,
            total_on_otomoto=total_on_otomoto,
            scraped=len(listings),
            pages_fetched=pages_fetched,
            truncated=truncated,
        )

    # Prefer majority currency if available
    currencies = [item.currency for item in listings if item.currency]
    if currencies:
        currency = max(set(currencies), key=currencies.count)

    return PriceStats(
        n=len(prices),
        n_without_price=n_without,
        median=float(statistics.median(prices)),
        mean=float(statistics.fmean(prices)),
        min=prices[0],
        max=prices[-1],
        q1=percentile_nearest_rank(prices, 25),
        q3=percentile_nearest_rank(prices, 75),
        currency=currency,
        total_on_otomoto=total_on_otomoto,
        scraped=len(listings),
        pages_fetched=pages_fetched,
        truncated=truncated,
    )


def group_by_year(listings: Sequence[Listing]) -> dict[int | None, list[Listing]]:
    groups: dict[int | None, list[Listing]] = {}
    for item in listings:
        groups.setdefault(item.year, []).append(item)
    return groups


def group_by_seller(listings: Sequence[Listing]) -> dict[str | None, list[Listing]]:
    groups: dict[str | None, list[Listing]] = {}
    for item in listings:
        groups.setdefault(item.seller_type, []).append(item)
    return groups
