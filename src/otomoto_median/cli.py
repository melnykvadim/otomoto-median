from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyze import analyze_search, format_report
from .fetcher import FetchError
from .parser import ParseError
from .telegram_notify import TelegramError, send_telegram_message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="otomoto-median",
        description="Scrape an OtoMoto search URL and report median listing prices.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="OtoMoto search/results URL with filters already applied",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=200,
        dest="max_listings",
        help="Maximum listings to collect (default: 200)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional hard cap on search pages",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Delay between page requests in seconds (default: 0.8)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON result instead of text report",
    )
    parser.add_argument(
        "--save-json",
        type=Path,
        default=None,
        help="Optional path to write full JSON result",
    )
    parser.add_argument(
        "--no-breakdowns",
        action="store_true",
        help="Hide year/seller breakdowns in text report",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Also send the text report to Telegram in Ukrainian (.secrets/telegram.env)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = analyze_search(
            args.url,
            max_listings=args.max_listings,
            max_pages=args.max_pages,
            delay_seconds=args.delay,
        )
    except (FetchError, ParseError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.save_json is not None:
        args.save_json.parent.mkdir(parents=True, exist_ok=True)
        args.save_json.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    include_breakdowns = not args.no_breakdowns
    report = format_report(result, include_breakdowns=include_breakdowns)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report)
        if args.save_json is not None:
            print(f"\nSaved JSON: {args.save_json}")

    if args.telegram:
        # Telegram replies are always Ukrainian.
        telegram_report = format_report(
            result, include_breakdowns=include_breakdowns, lang="uk"
        )
        try:
            send_telegram_message(telegram_report)
        except TelegramError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print("\nSent to Telegram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
