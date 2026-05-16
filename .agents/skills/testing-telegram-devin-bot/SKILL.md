---
name: testing-telegram-devin-bot
description: Test the devin-smoky Telegram-to-Devin bot webhook using live Telegram and Devin credentials.
---

# Testing Telegram Devin Bot

## Devin Secrets Needed
- `TELEGRAM_BOT_TOKEN`: Bot token from BotFather.
- `DEVIN_API_KEY`: Devin service-user API key, should start with `cog_`.
- `DEVIN_ORG_ID`: Devin organization ID, should start with `org-`.
- Optional: `TELEGRAM_ALLOWED_USER_IDS` to restrict bot access.

## Setup
1. Install dependencies with `poetry install`.
2. Create a local `.env` file from the secrets. Do not commit it.
3. Include `TELEGRAM_WEBHOOK_SECRET` with a random value.
4. For a temporary test, run:
   ```bash
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. Expose port 8000 or deploy the backend publicly. For persistent SQLite deployments, use a `/data` volume.
6. Configure Telegram webhook:
   ```bash
   poetry run python scripts/set_telegram_webhook.py https://<public-host>/telegram/webhook
   ```

## Validation
1. Confirm `/health` returns HTTP 200 through the public URL.
2. Confirm Telegram `getWebhookInfo` reports `ok=true`, `pending_update_count=0`, and no `last_error_message`.
3. Ask the Telegram user to send `/start`, a normal message, and `/where`.
4. Watch server logs for POST `/telegram/webhook` responses with HTTP 200.
5. Check SQLite has a chat-to-session mapping if session persistence is expected.

## Notes
- Temporary exposed URLs may contain basic-auth credentials; do not paste them into reports or PR descriptions.
- If permanent deployment to Fly.io fails with a machine-limit error, the user or org admin needs to free/increase the machine quota before retrying.
- If `TELEGRAM_ALLOWED_USER_IDS` is empty, anyone with the bot username can use the bot while it is running.
