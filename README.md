# OtoMoto median price analyzer

CLI tool that takes an OtoMoto search URL (with filters already applied), scrapes listing cards, and reports **median / Q1 / Q3** prices plus breakdowns by year and seller type.

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m otomoto_median --url "https://www.otomoto.pl/osobowe/toyota/corolla" --max 96
```

Example with a filtered URL from the OtoMoto UI:

```bash
python -m otomoto_median \
  --url "https://www.otomoto.pl/osobowe/uzywane/toyota/corolla?search%5Bfilter_float_year%3Afrom%5D=2018&search%5Bfilter_float_year%3Ato%5D=2021" \
  --max 160 \
  --save-json out.json
```

## CLI options

| Flag | Meaning |
|------|---------|
| `--url` | Required OtoMoto search/results URL |
| `--max` | Max listings to collect (default 200) |
| `--max-pages` | Optional hard page cap |
| `--delay` | Seconds between page requests (default 0.8) |
| `--json` | Print full JSON to stdout |
| `--save-json PATH` | Write full JSON result to a file |
| `--no-breakdowns` | Hide year/seller sections in text report |
| `--telegram` | Send the text report via Telegram Bot API |

## Telegram

1. Copy `telegram.env.example` → `.secrets/telegram.env`
2. Fill `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
3. Run with `--telegram`:

```bash
python -m otomoto_median --url "https://www.otomoto.pl/osobowe/toyota/corolla" --max 64 --telegram
```

`.secrets/` is gitignored — never commit the bot token.

## How it works

1. Fetch search HTML.
2. Parse embedded `__NEXT_DATA__` → `urqlState` → `advertSearch.edges`.
3. Paginate with `?page=N` until the listing cap / last page.
4. Drop missing/zero prices, compute median + quartiles.
5. Also report breakdowns by year and seller (`private` / `professional`).

## Notes

- OtoMoto has no public API; this reads public search pages.
- Be polite: keep `--delay` reasonable and avoid huge crawls.
- If DataDome blocks requests, retry later or use a residential proxy.
- Median alone is a market anchor; Q1–Q3 and year/seller splits give better context.

## Tests

```bash
python -m pytest -q
```
