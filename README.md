# devin-smoky

Telegram bot bridge for chatting with Devin from Telegram.

## What it does

- Receives Telegram messages through a FastAPI webhook.
- Creates or reuses a Devin session for each Telegram chat.
- Sends normal Telegram messages to Devin.
- Supports `/new`, `/session`, `/where`, `/messages`, and `/help` commands.
- Stores chat-to-session mappings in SQLite.

## Required secrets

Create these environment variables before running the service:

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather). |
| `DEVIN_API_KEY` | Devin service-user API key starting with `cog_`. |
| `DEVIN_ORG_ID` | Devin organization ID, for example `org-...`. |
| `TELEGRAM_WEBHOOK_SECRET` | Random secret sent by Telegram in the webhook header. |
| `TELEGRAM_ALLOWED_USER_IDS` | Optional comma-separated Telegram user IDs allowed to use the bot. |
| `DEVIN_DEFAULT_SESSION_ID` | Optional existing Devin session ID to use before `/new` is called. |
| `DATA_DIR` | Optional data directory. Defaults to `/data` when that volume exists, otherwise `data`. |

Create the Devin API key from Devin Settings → Service users. The service user needs `ManageOrgSessions` and `ViewOrgSessions`; use the Member role for normal automation.

## Run locally

```bash
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Set the Telegram webhook

After deploying the FastAPI app to a public HTTPS URL:

```bash
export TELEGRAM_WEBHOOK_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
poetry run python scripts/set_telegram_webhook.py https://your-public-url.example.com/telegram/webhook
```

## Bot commands

- `/start` or `/help` — show help.
- `/new <prompt>` — create a new Devin session and store it for this chat.
- `/session devin-...` — attach this Telegram chat to an existing Devin session.
- `/where` — show the current Devin session link.
- `/messages` — fetch recent messages from the current Devin session.

Normal text messages are sent to the current Devin session. If no session is selected and `DEVIN_DEFAULT_SESSION_ID` is unset, the first message creates a new Devin session.
