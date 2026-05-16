from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request

from app.config import get_settings
from app.store import SessionStore
from app.telegram_bot import build_bot
from app.types import JSONValue

settings = get_settings()
store = SessionStore(settings.sqlite_path)
bot = build_bot(settings, store)
app = FastAPI(title="devin-smoky")


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "devin-smoky", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[
        str | None,
        Header(alias="X-Telegram-Bot-Api-Secret-Token"),
    ] = None,
) -> dict[str, bool]:
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload: JSONValue = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Telegram update")

    await bot.handle_update(payload)
    return {"ok": True}
