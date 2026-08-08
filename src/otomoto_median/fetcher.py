from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Callable


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    """Raised when OtoMoto HTML cannot be fetched."""


def fetch_html(
    url: str,
    *,
    timeout: float = 30.0,
    user_agent: str = DEFAULT_USER_AGENT,
    retries: int = 3,
    backoff: float = 1.5,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """GET a page and return UTF-8 HTML with retries/backoff."""
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 >= retries:
                break
            sleeper(backoff * (2**attempt))
    raise FetchError(f"Failed to fetch {url}: {last_error}") from last_error
