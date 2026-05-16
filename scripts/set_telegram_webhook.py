from __future__ import annotations

import sys

import httpx
from app.config import get_settings


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/set_telegram_webhook.py https://example.com/telegram/webhook")
        return 2

    settings = get_settings()
    if not settings.telegram_bot_token:
        print("TELEGRAM_BOT_TOKEN is required")
        return 2
    if not settings.telegram_webhook_secret:
        print("TELEGRAM_WEBHOOK_SECRET is required")
        return 2

    response = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
        json={"url": sys.argv[1], "secret_token": settings.telegram_webhook_secret},
        timeout=20.0,
    )
    response.raise_for_status()
    print("Telegram webhook configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
