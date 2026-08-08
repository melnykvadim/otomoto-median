from __future__ import annotations

import json

from otomoto_median.analyze import analyze_search, format_report, infer_vehicle_label
from otomoto_median.parser import with_page, with_price_order_asc


def _page_html(ids_prices: list[tuple[str, int]], *, total: int, offset: int, page_size: int = 2) -> str:
    edges = []
    for listing_id, price in ids_prices:
        edges.append(
            {
                "node": {
                    "id": listing_id,
                    "title": f"Car {listing_id}",
                    "url": f"https://www.otomoto.pl/osobowe/oferta/{listing_id}.html",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "price": {
                        "amount": {"units": price, "value": str(price), "currencyCode": "PLN"}
                    },
                    "location": {"city": {"name": "Warszawa"}, "region": {"name": "Mazowieckie"}},
                    "seller": {"__typename": "PrivateSeller"},
                    "parameters": [
                        {"key": "year", "value": "2019"},
                        {"key": "mileage", "value": "100000"},
                        {"key": "make", "value": "toyota"},
                        {"key": "model", "value": "corolla"},
                    ],
                }
            }
        )
    advert_search = {
        "totalCount": total,
        "pageInfo": {"pageSize": page_size, "currentOffset": offset},
        "url": "https://www.otomoto.pl/osobowe/toyota/corolla",
        "edges": edges,
    }
    next_data = {
        "props": {
            "pageProps": {
                "urqlState": {"x": {"data": json.dumps({"advertSearch": advert_search})}}
            }
        }
    }
    return (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        "</body></html>"
    )


def test_analyze_search_paginates_and_dedups():
    base = with_price_order_asc("https://www.otomoto.pl/osobowe/toyota/corolla")
    pages = {
        base: _page_html([("1", 40_000), ("2", 50_000)], total=4, offset=0),
        with_page(base, 2): _page_html([("2", 50_000), ("3", 60_000)], total=4, offset=2),
        with_page(base, 3): _page_html([("4", 70_000)], total=4, offset=4, page_size=2),
    }

    def fake_fetch(url: str) -> str:
        return pages[url]

    result = analyze_search(
        "https://www.otomoto.pl/osobowe/toyota/corolla",
        max_listings=10,
        delay_seconds=0,
        fetch=fake_fetch,
        sleeper=lambda _: None,
    )
    assert [item.id for item in result.listings] == ["1", "2", "3", "4"]
    assert result.stats.n == 4
    assert result.stats.median == 55_000
    assert result.stats.pages_fetched == 3
    assert "filter_float_price" in result.search_url
    assert "asc" in result.search_url
    report = format_report(result)
    assert "Median:" in report
    assert "55 000 PLN" in report or "55000 PLN" in report.replace(" ", "")
    assert "filter_float_price" in report

    uk_report = format_report(result, lang="uk")
    assert "Аналіз цін OtoMoto" in uk_report
    assert "Авто: Toyota Corolla" in uk_report
    assert "Медіана:" in uk_report
    assert "За типом продавця:" in uk_report
    assert "приватний:" in uk_report
    assert "Median:" not in uk_report

    assert "Vehicle: Toyota Corolla" in report


def test_infer_vehicle_label_uses_filters():
    from otomoto_median.models import Listing, PriceStats
    from otomoto_median.analyze import AnalysisResult

    listings = [
        Listing(
            id="1",
            title="Volkswagen Golf 1.6 TDI",
            url="https://example.com/1",
            price=30_000,
            currency="PLN",
            year=2016,
            mileage_km=100_000,
            fuel_type="diesel",
            gearbox="manual",
            make="volkswagen",
            model="golf",
            city="Warszawa",
            region="Mazowieckie",
            seller_type="private",
            created_at=None,
        )
    ]
    stats = PriceStats(
        n=1,
        n_without_price=0,
        median=30_000,
        mean=30_000,
        min=30_000,
        max=30_000,
        q1=30_000,
        q3=30_000,
        currency="PLN",
        total_on_otomoto=1,
        scraped=1,
        pages_fetched=1,
        truncated=False,
    )
    result = AnalysisResult(
        search_url=(
            "https://www.otomoto.pl/osobowe/volkswagen/golf"
            "?search%5Bfilter_float_year%3Afrom%5D=2016"
            "&search%5Bfilter_float_year%3Ato%5D=2016"
            "&search%5Bfilter_float_engine_capacity%3Afrom%5D=1500"
            "&search%5Bfilter_float_engine_capacity%3Ato%5D=1700"
            "&search%5Bfilter_enum_fuel_type%5D%5B0%5D=diesel"
        ),
        listings=listings,
        stats=stats,
        by_year={"2016": stats},
        by_seller={"private": stats},
    )
    assert infer_vehicle_label(result, lang="uk") == "Volkswagen Golf 1.6 · 2016 · дизель"
    report = format_report(result, lang="uk")
    assert "Авто: Volkswagen Golf 1.6 · 2016 · дизель" in report
