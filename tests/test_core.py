from __future__ import annotations

import json

from otomoto_median.models import Listing
from otomoto_median.parser import parse_search_page, with_page, with_price_order_asc
from otomoto_median.stats import compute_stats, percentile_nearest_rank


def _listing(price: int | None, *, year: int | None = 2019, seller: str | None = "private") -> Listing:
    return Listing(
        id=f"id-{price}-{year}-{seller}",
        title="Test",
        url="https://example.com",
        price=price,
        currency="PLN",
        year=year,
        mileage_km=100000,
        fuel_type="hybrid",
        gearbox="automatic",
        make="toyota",
        model="corolla",
        city="Warszawa",
        region="Mazowieckie",
        seller_type=seller,
        created_at=None,
    )


def test_percentile_and_median():
    prices = [10, 20, 30, 40, 50]
    assert percentile_nearest_rank(prices, 25) == 10
    assert percentile_nearest_rank(prices, 75) == 40
    stats = compute_stats([_listing(p) for p in prices])
    assert stats.n == 5
    assert stats.median == 30
    assert stats.min == 10
    assert stats.max == 50


def test_ignores_missing_prices():
    listings = [_listing(100), _listing(None), _listing(0), _listing(200)]
    stats = compute_stats(listings)
    assert stats.n == 2
    assert stats.n_without_price == 2
    assert stats.median == 150


def test_with_page_preserves_filters():
    url = "https://www.otomoto.pl/osobowe/toyota/corolla?search%5Bfilter_float_year%3Afrom%5D=2018"
    out = with_page(url, 3)
    assert "page=3" in out
    assert "filter_float_year%3Afrom" in out or "filter_float_year:from" in out


def test_with_price_order_asc_sets_and_overrides():
    url = (
        "https://www.otomoto.pl/osobowe/toyota/corolla"
        "?search%5Bfilter_float_year%3Afrom%5D=2018"
        "&search%5Border%5D=created_at%3Adesc"
    )
    out = with_price_order_asc(url)
    assert "filter_float_year%3Afrom" in out or "filter_float_year:from" in out
    assert "search%5Border%5D=filter_float_price%3Aasc" in out
    assert "created_at" not in out


def test_parse_search_page_from_fixture():
    advert_search = {
        "totalCount": 2,
        "pageInfo": {"pageSize": 32, "currentOffset": 0},
        "url": "https://www.otomoto.pl/osobowe/toyota/corolla",
        "edges": [
            {
                "node": {
                    "id": "1",
                    "title": "Toyota Corolla",
                    "url": "https://www.otomoto.pl/osobowe/oferta/x.html",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "price": {
                        "amount": {"units": 50000, "value": "50000", "currencyCode": "PLN"}
                    },
                    "location": {
                        "city": {"name": "Kraków"},
                        "region": {"name": "Małopolskie"},
                    },
                    "seller": {"__typename": "PrivateSeller"},
                    "parameters": [
                        {"key": "year", "value": "2018"},
                        {"key": "mileage", "value": "90000"},
                        {"key": "make", "value": "toyota"},
                        {"key": "model", "value": "corolla"},
                        {"key": "fuel_type", "value": "petrol"},
                        {"key": "gearbox", "value": "manual"},
                    ],
                }
            },
            {
                "node": {
                    "id": "2",
                    "title": "Toyota Corolla Hybrid",
                    "url": "https://www.otomoto.pl/osobowe/oferta/y.html",
                    "createdAt": "2026-01-02T00:00:00Z",
                    "price": {
                        "amount": {"units": 70000, "value": "70000", "currencyCode": "PLN"}
                    },
                    "location": {
                        "city": {"name": "Gdańsk"},
                        "region": {"name": "Pomorskie"},
                    },
                    "seller": {"__typename": "ProfessionalSeller"},
                    "parameters": [
                        {"key": "year", "value": "2020"},
                        {"key": "mileage", "value": "40000"},
                        {"key": "make", "value": "toyota"},
                        {"key": "model", "value": "corolla"},
                    ],
                }
            },
        ],
    }
    next_data = {
        "props": {
            "pageProps": {
                "urqlState": {
                    "abc": {"data": json.dumps({"advertSearch": advert_search})}
                }
            }
        }
    }
    html = (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        "</body></html>"
    )
    listings, meta = parse_search_page(html)
    assert meta["total_count"] == 2
    assert len(listings) == 2
    assert listings[0].price == 50000
    assert listings[0].seller_type == "private"
    assert listings[1].seller_type == "professional"
    assert listings[0].year == 2018
    assert listings[1].mileage_km == 40000
