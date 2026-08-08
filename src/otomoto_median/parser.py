from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .models import Listing

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
    re.DOTALL,
)


class ParseError(RuntimeError):
    """Raised when OtoMoto HTML cannot be parsed into listings."""


def extract_next_data(html: str) -> dict[str, Any]:
    match = NEXT_DATA_RE.search(html)
    if not match:
        if "datadome" in html.lower() and "captcha" in html.lower():
            raise ParseError(
                "OtoMoto returned an anti-bot challenge (DataDome). "
                "Retry later or use a residential proxy."
            )
        raise ParseError("__NEXT_DATA__ not found in page HTML")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid __NEXT_DATA__ JSON: {exc}") from exc


def _parse_urql_payload(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    if isinstance(raw, dict):
        return raw
    return None


def extract_advert_search(next_data: dict[str, Any]) -> dict[str, Any]:
    try:
        urql_state = next_data["props"]["pageProps"]["urqlState"]
    except (KeyError, TypeError) as exc:
        raise ParseError("pageProps.urqlState missing") from exc

    for entry in urql_state.values():
        if not isinstance(entry, dict):
            continue
        payload = _parse_urql_payload(entry.get("data"))
        if payload and isinstance(payload.get("advertSearch"), dict):
            return payload["advertSearch"]
    raise ParseError("advertSearch payload not found in urqlState")


def _param_map(parameters: list[dict[str, Any]] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not parameters:
        return out
    for item in parameters:
        key = item.get("key")
        value = item.get("value")
        if isinstance(key, str) and value is not None:
            out[key] = str(value)
    return out


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(" ", "").replace("\xa0", "")
    if not text:
        return None
    # mileage sometimes like "102000 km" already normalized in value field
    digits = re.sub(r"[^\d-]", "", text)
    if not digits or digits == "-":
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _seller_type(node: dict[str, Any]) -> str | None:
    seller = node.get("seller")
    if not isinstance(seller, dict):
        return None
    typename = str(seller.get("__typename") or "")
    lower = typename.lower()
    if "professional" in lower or "business" in lower or "dealer" in lower:
        return "professional"
    if "private" in lower or "personal" in lower:
        return "private"
    return typename or None


def parse_listing(node: dict[str, Any]) -> Listing:
    params = _param_map(node.get("parameters"))
    price_block = node.get("price") or {}
    amount = price_block.get("amount") or {}
    price = _to_int(amount.get("units") if amount.get("units") is not None else amount.get("value"))
    currency = amount.get("currencyCode")
    location = node.get("location") or {}
    city = ((location.get("city") or {}) or {}).get("name")
    region = ((location.get("region") or {}) or {}).get("name")

    return Listing(
        id=str(node.get("id") or ""),
        title=str(node.get("title") or ""),
        url=str(node.get("url") or ""),
        price=price if price and price > 0 else None,
        currency=str(currency) if currency else None,
        year=_to_int(params.get("year")),
        mileage_km=_to_int(params.get("mileage")),
        fuel_type=params.get("fuel_type"),
        gearbox=params.get("gearbox"),
        make=params.get("make"),
        model=params.get("model"),
        city=str(city) if city else None,
        region=str(region) if region else None,
        seller_type=_seller_type(node),
        created_at=str(node.get("createdAt")) if node.get("createdAt") else None,
    )


def parse_search_page(html: str) -> tuple[list[Listing], dict[str, Any]]:
    """Parse one search HTML page into listings + metadata."""
    next_data = extract_next_data(html)
    advert_search = extract_advert_search(next_data)
    edges = advert_search.get("edges") or []
    listings: list[Listing] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node")
        if isinstance(node, dict):
            listing = parse_listing(node)
            if listing.id:
                listings.append(listing)

    meta = {
        "total_count": advert_search.get("totalCount"),
        "page_size": (advert_search.get("pageInfo") or {}).get("pageSize") or 32,
        "current_offset": (advert_search.get("pageInfo") or {}).get("currentOffset") or 0,
        "url": advert_search.get("url"),
    }
    return listings, meta


def _set_query_params(url: str, updates: dict[str, str | None]) -> str:
    """Set or remove query params while preserving existing filters."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in updates.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = [value]
    pairs: list[tuple[str, str]] = []
    for key, values in query.items():
        for item in values:
            pairs.append((key, item))
    new_query = urlencode(pairs, doseq=False)
    return urlunparse(parsed._replace(query=new_query))


def with_price_order_asc(url: str) -> str:
    """Ensure OtoMoto search URL sorts listings by price ascending."""
    return _set_query_params(url, {"search[order]": "filter_float_price:asc"})


def with_page(url: str, page: int) -> str:
    """Return search URL with page query set (1-based)."""
    if page < 1:
        raise ValueError("page must be >= 1")
    return _set_query_params(url, {"page": str(page)})
