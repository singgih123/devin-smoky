from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings
from app.devin_client import (
    DevinClient,
    DevinConfigurationError,
    format_recent_messages,
    normalize_session_id,
    session_web_url,
)
from app.store import SessionStore
from app.types import JSONObject, JSONValue

HELP_TEXT = """Kirim pesan biasa untuk meneruskan instruksi ke Devin.

Perintah:
/start atau /help - tampilkan bantuan
/new <prompt> - buat sesi Devin baru
/session devin-... - pakai sesi Devin yang sudah ada
/where - lihat sesi aktif
/messages - ambil pesan terbaru dari sesi aktif"""


class TelegramConfigurationError(RuntimeError):
    pass


class TelegramSender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> None:
        raise NotImplementedError


class DevinSessionClient(Protocol):
    async def create_session(self, prompt: str) -> str:
        raise NotImplementedError

    async def send_message(self, session_id: str, message: str) -> None:
        raise NotImplementedError

    async def list_messages(self, session_id: str) -> JSONObject:
        raise NotImplementedError


@dataclass(frozen=True)
class TelegramMessage:
    chat_id: int
    user_id: int | None
    text: str


class TelegramClient:
    def __init__(self, token: str) -> None:
        self.token = token

    async def send_message(self, chat_id: int, text: str) -> None:
        if not self.token:
            raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN must be configured")

        for chunk in split_telegram_message(text):
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload: JSONObject = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json=payload)
            response.raise_for_status()


class BotService:
    def __init__(
        self,
        settings: Settings,
        store: SessionStore,
        telegram: TelegramSender,
        devin: DevinSessionClient,
    ) -> None:
        self.settings = settings
        self.store = store
        self.telegram = telegram
        self.devin = devin

    async def handle_update(self, update: JSONObject) -> None:
        message = extract_telegram_message(update)
        if message is None:
            return

        allowed_user_ids = self.settings.allowed_user_ids
        if allowed_user_ids and message.user_id not in allowed_user_ids:
            await self.telegram.send_message(message.chat_id, "User Telegram ini belum diizinkan.")
            return

        try:
            await self._process_message(message)
        except (DevinConfigurationError, TelegramConfigurationError) as error:
            await self.telegram.send_message(message.chat_id, f"Konfigurasi belum lengkap: {error}")
        except httpx.HTTPStatusError as error:
            await self.telegram.send_message(
                message.chat_id,
                f"API mengembalikan error HTTP {error.response.status_code}.",
            )
        except httpx.HTTPError:
            await self.telegram.send_message(message.chat_id, "Gagal menghubungi API eksternal.")

    async def _process_message(self, message: TelegramMessage) -> None:
        text = message.text.strip()
        if not text:
            return

        if text.startswith("/"):
            await self._process_command(message.chat_id, text)
            return

        session_id = (
            self.store.get_session(message.chat_id) or self.settings.devin_default_session_id
        )
        if session_id:
            session_id = normalize_session_id(session_id)
            self.store.set_session(message.chat_id, session_id)
            await self.devin.send_message(session_id, text)
            await self.telegram.send_message(
                message.chat_id,
                f"Terkirim ke Devin: {session_web_url(session_id)}",
            )
            return

        session_id = await self.devin.create_session(text)
        self.store.set_session(message.chat_id, session_id)
        await self.telegram.send_message(
            message.chat_id,
            f"Sesi Devin baru dibuat: {session_web_url(session_id)}",
        )

    async def _process_command(self, chat_id: int, text: str) -> None:
        parts = text.split(maxsplit=1)
        command = parts[0].split("@", maxsplit=1)[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command in {"/start", "/help"}:
            await self.telegram.send_message(chat_id, HELP_TEXT)
            return

        if command == "/new":
            prompt = argument or "Mulai sesi Telegram baru dengan Devin."
            session_id = await self.devin.create_session(prompt)
            self.store.set_session(chat_id, session_id)
            await self.telegram.send_message(chat_id, f"Sesi baru: {session_web_url(session_id)}")
            return

        if command == "/session":
            if not argument:
                await self.telegram.send_message(chat_id, "Format: /session devin-...")
                return
            session_id = normalize_session_id(argument)
            self.store.set_session(chat_id, session_id)
            await self.telegram.send_message(chat_id, f"Sesi aktif: {session_web_url(session_id)}")
            return

        if command == "/where":
            session_id = self.store.get_session(chat_id) or self.settings.devin_default_session_id
            if not session_id:
                await self.telegram.send_message(
                    chat_id,
                    "Belum ada sesi aktif. Pakai /new <prompt>.",
                )
                return
            await self.telegram.send_message(chat_id, f"Sesi aktif: {session_web_url(session_id)}")
            return

        if command == "/messages":
            session_id = self.store.get_session(chat_id) or self.settings.devin_default_session_id
            if not session_id:
                await self.telegram.send_message(
                    chat_id,
                    "Belum ada sesi aktif. Pakai /new <prompt>.",
                )
                return
            data = await self.devin.list_messages(session_id)
            await self.telegram.send_message(chat_id, format_recent_messages(data))
            return

        await self.telegram.send_message(chat_id, "Perintah tidak dikenal. Pakai /help.")


def extract_telegram_message(update: JSONObject) -> TelegramMessage | None:
    message_value = update.get("message") or update.get("edited_message")
    if not isinstance(message_value, dict):
        return None

    chat_value = message_value.get("chat")
    from_value = message_value.get("from")
    text_value = message_value.get("text")
    if not isinstance(chat_value, dict) or not isinstance(text_value, str):
        return None

    chat_id = extract_int(chat_value.get("id"))
    if chat_id is None:
        return None

    user_id: int | None = None
    if isinstance(from_value, dict):
        user_id = extract_int(from_value.get("id"))

    return TelegramMessage(chat_id=chat_id, user_id=user_id, text=text_value)


def extract_int(value: JSONValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def split_telegram_message(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        chunks.append(remaining[:limit])
        remaining = remaining[limit:]
    return chunks


def build_bot(settings: Settings, store: SessionStore) -> BotService:
    telegram = TelegramClient(settings.telegram_bot_token)
    devin = DevinClient(settings.devin_api_key, settings.devin_org_id, settings.devin_base_url)
    return BotService(settings=settings, store=store, telegram=telegram, devin=devin)
