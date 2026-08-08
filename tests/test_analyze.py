from __future__ import annotations

import json

from otomoto_median.analyze import analyze_search, format_report


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
    pages = {
        "https://www.otomoto.pl/osobowe/toyota/corolla": _page_html(
            [("1", 40_000), ("2", 50_000)], total=4, offset=0
        ),
        "https://www.otomoto.pl/osobowe/toyota/corolla?page=2": _page_html(
            [("2", 50_000), ("3", 60_000)], total=4, offset=2
        ),
        "https://www.otomoto.pl/osobowe/toyota/corolla?page=3": _page_html(
            [("4", 70_000)], total=4, offset=4, page_size=2
        ),
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
    report = format_report(result)
    assert "Median:" in report
    assert "55 000 PLN" in report or "55000 PLN" in report.replace(" ", "")
