from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


class TelegramError(RuntimeError):
    pass


def load_telegram_env(env_file: Path | None = None) -> tuple[str, str]:
    """Load TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env or .secrets/telegram.env."""
    candidates: list[Path] = []
    if env_file is not None:
        candidates.append(env_file)
    else:
        candidates.extend(
            [
                Path.cwd() / ".secrets" / "telegram.env",
                Path(__file__).resolve().parents[2] / ".secrets" / "telegram.env",
            ]
        )

    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        raise TelegramError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. "
            "Put them in .secrets/telegram.env or export in the environment."
        )
    return token, chat_id


def send_telegram_message(text: str, *, env_file: Path | None = None) -> dict:
    token, chat_id = load_telegram_env(env_file)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": text},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise TelegramError(f"Telegram HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise TelegramError(f"Telegram request failed: {exc}") from exc

    if not body.get("ok"):
        raise TelegramError(f"Telegram API error: {body}")
    return body
