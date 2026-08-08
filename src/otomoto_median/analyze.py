from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .fetcher import fetch_html
from .models import Listing, PriceStats
from .parser import parse_search_page, with_page
from .stats import compute_stats, group_by_seller, group_by_year, valid_prices


@dataclass
class AnalysisResult:
    search_url: str
    listings: list[Listing]
    stats: PriceStats
    by_year: dict[str, PriceStats]
    by_seller: dict[str, PriceStats]

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_url": self.search_url,
            "stats": self.stats.to_dict(),
            "by_year": {k: v.to_dict() for k, v in self.by_year.items()},
            "by_seller": {k: v.to_dict() for k, v in self.by_seller.items()},
            "listings": [item.to_dict() for item in self.listings],
        }


def analyze_search(
    search_url: str,
    *,
    max_listings: int = 200,
    max_pages: int | None = None,
    delay_seconds: float = 0.8,
    fetch: Callable[[str], str] = fetch_html,
    sleeper: Callable[[float], None] = time.sleep,
) -> AnalysisResult:
    """Fetch paginated OtoMoto search results and compute price stats."""
    if max_listings < 1:
        raise ValueError("max_listings must be >= 1")

    collected: list[Listing] = []
    seen_ids: set[str] = set()
    total_count: int | None = None
    page_size = 32
    pages_fetched = 0
    truncated = False

    page = 1
    while True:
        if max_pages is not None and page > max_pages:
            truncated = True
            break
        if len(collected) >= max_listings:
            truncated = True
            break

        page_url = with_page(search_url, page) if page > 1 else search_url
        html = fetch(page_url)
        listings, meta = parse_search_page(html)
        pages_fetched += 1

        if total_count is None:
            total_count = meta.get("total_count")
        page_size = int(meta.get("page_size") or page_size)

        new_on_page = 0
        for listing in listings:
            if listing.id in seen_ids:
                continue
            seen_ids.add(listing.id)
            collected.append(listing)
            new_on_page += 1
            if len(collected) >= max_listings:
                truncated = True
                break

        # Stop when page is empty or shorter than page size (last page)
        if new_on_page == 0 or len(listings) < page_size:
            break
        if total_count is not None and len(collected) >= total_count:
            break

        page += 1
        if delay_seconds > 0:
            sleeper(delay_seconds)

    # If we stopped early vs OtoMoto total, mark truncated
    if total_count is not None and len(collected) < total_count and (
        max_pages is not None or len(collected) >= max_listings
    ):
        truncated = True

    overall = compute_stats(
        collected,
        total_on_otomoto=total_count,
        pages_fetched=pages_fetched,
        truncated=truncated,
    )

    by_year: dict[str, PriceStats] = {}
    for year, group in sorted(group_by_year(collected).items(), key=lambda x: (x[0] is None, x[0])):
        key = "unknown" if year is None else str(year)
        by_year[key] = compute_stats(group)

    by_seller: dict[str, PriceStats] = {}
    for seller, group in sorted(
        group_by_seller(collected).items(), key=lambda x: (x[0] is None, str(x[0]))
    ):
        key = "unknown" if seller is None else seller
        by_seller[key] = compute_stats(group)

    return AnalysisResult(
        search_url=search_url,
        listings=collected,
        stats=overall,
        by_year=by_year,
        by_seller=by_seller,
    )


_SELLER_LABELS_UK = {
    "private": "приватний",
    "professional": "дилер",
    "unknown": "невідомо",
}


def format_money(
    value: float | int | None,
    currency: str = "PLN",
    *,
    lang: str = "en",
) -> str:
    if value is None:
        return "н/д" if lang == "uk" else "n/a"
    return f"{int(round(value)):,} {currency}".replace(",", " ")


def _seller_label(key: str, *, lang: str) -> str:
    if lang == "uk":
        return _SELLER_LABELS_UK.get(key, key)
    return key


def format_report(
    result: AnalysisResult,
    *,
    include_breakdowns: bool = True,
    lang: str = "en",
) -> str:
    """Format analysis as text. Use lang='uk' for Ukrainian (Telegram default)."""
    s = result.stats

    if lang == "uk":
        scraped = (
            f"Зібрано: {s.scraped} оголошень з {s.pages_fetched} стор."
            + (
                f" (усього на OtoMoto: {s.total_on_otomoto})"
                if s.total_on_otomoto is not None
                else ""
            )
        )
        with_price = (
            f"З ціною: {s.n} | без/некоректна ціна: {s.n_without_price}"
            + (" | обрізано=так" if s.truncated else "")
        )
        lines = [
            "Аналіз цін OtoMoto",
            f"URL: {result.search_url}",
            scraped,
            with_price,
            "",
            f"Медіана: {format_money(s.median, s.currency, lang=lang)}",
            f"Q1–Q3:  {format_money(s.q1, s.currency, lang=lang)} – "
            f"{format_money(s.q3, s.currency, lang=lang)}",
            f"Мін–Макс: {format_money(s.min, s.currency, lang=lang)} – "
            f"{format_money(s.max, s.currency, lang=lang)}",
            f"Середнє: {format_money(s.mean, s.currency, lang=lang)}",
        ]
        seller_header = "За типом продавця:"
        year_header = "За роком (n≥3):"
        year_empty = "  (недостатньо вибірки по роках)"
        sample_line = "Розмір вибірки для медіани: {n}"
        median_word = "медіана"
    else:
        scraped = (
            f"Scraped: {s.scraped} listings across {s.pages_fetched} page(s)"
            + (
                f" (OtoMoto totalCount={s.total_on_otomoto})"
                if s.total_on_otomoto is not None
                else ""
            )
        )
        with_price = (
            f"With price: {s.n} | without/invalid price: {s.n_without_price}"
            + (" | truncated=yes" if s.truncated else "")
        )
        lines = [
            "OtoMoto price analysis",
            f"URL: {result.search_url}",
            scraped,
            with_price,
            "",
            f"Median: {format_money(s.median, s.currency, lang=lang)}",
            f"Q1–Q3:  {format_money(s.q1, s.currency, lang=lang)} – "
            f"{format_money(s.q3, s.currency, lang=lang)}",
            f"Min–Max: {format_money(s.min, s.currency, lang=lang)} – "
            f"{format_money(s.max, s.currency, lang=lang)}",
            f"Mean:   {format_money(s.mean, s.currency, lang=lang)}",
        ]
        seller_header = "By seller type:"
        year_header = "By year (n>=3):"
        year_empty = "  (not enough per-year samples)"
        sample_line = "Price sample size used for median: {n}"
        median_word = "median"

    if include_breakdowns and result.by_seller:
        lines.append("")
        lines.append(seller_header)
        for key, stats in result.by_seller.items():
            label = _seller_label(key, lang=lang)
            lines.append(
                f"  - {label}: {median_word} "
                f"{format_money(stats.median, stats.currency, lang=lang)} (n={stats.n})"
            )

    if include_breakdowns and result.by_year:
        lines.append("")
        lines.append(year_header)
        shown = 0
        for key, stats in result.by_year.items():
            if stats.n < 3:
                continue
            year_label = "невідомо" if lang == "uk" and key == "unknown" else key
            lines.append(
                f"  - {year_label}: {median_word} "
                f"{format_money(stats.median, stats.currency, lang=lang)} "
                f"(n={stats.n}, Q1={format_money(stats.q1, stats.currency, lang=lang)}, "
                f"Q3={format_money(stats.q3, stats.currency, lang=lang)})"
            )
            shown += 1
        if shown == 0:
            lines.append(year_empty)

    prices = valid_prices(result.listings)
    if prices:
        lines.append("")
        lines.append(sample_line.format(n=len(prices)))

    return "\n".join(lines)
