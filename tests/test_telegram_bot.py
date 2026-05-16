from pathlib import Path

import pytest
from app.config import Settings
from app.store import SessionStore
from app.telegram_bot import BotService, extract_telegram_message, split_telegram_message
from app.types import JSONObject


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class FakeDevin:
    def __init__(self) -> None:
        self.created_prompts: list[str] = []
        self.sent_messages: list[tuple[str, str]] = []

    async def create_session(self, prompt: str) -> str:
        self.created_prompts.append(prompt)
        return "devin-created"

    async def send_message(self, session_id: str, message: str) -> None:
        self.sent_messages.append((session_id, message))

    async def list_messages(self, session_id: str) -> JSONObject:
        return {"messages": [{"role": "assistant", "message": f"latest from {session_id}"}]}


def make_update(text: str, user_id: int = 123, chat_id: int = 456) -> JSONObject:
    return {
        "message": {
            "text": text,
            "from": {"id": user_id},
            "chat": {"id": chat_id},
        }
    }


def make_bot(
    tmp_path: Path,
    allowed_user_ids: str = "123",
) -> tuple[BotService, FakeTelegram, FakeDevin]:
    settings = Settings(telegram_allowed_user_ids=allowed_user_ids, data_dir=tmp_path)
    store = SessionStore(settings.sqlite_path)
    telegram = FakeTelegram()
    devin = FakeDevin()
    return BotService(settings, store, telegram, devin), telegram, devin


def test_extract_telegram_message() -> None:
    message = extract_telegram_message(make_update("halo"))

    assert message is not None
    assert message.chat_id == 456
    assert message.user_id == 123
    assert message.text == "halo"


def test_split_telegram_message_chunks_long_text() -> None:
    chunks = split_telegram_message("abcde", limit=2)

    assert chunks == ["ab", "cd", "e"]


@pytest.mark.asyncio
async def test_first_normal_message_creates_session(tmp_path) -> None:
    bot, telegram, devin = make_bot(tmp_path)

    await bot.handle_update(make_update("tolong cek repo"))

    assert devin.created_prompts == ["tolong cek repo"]
    assert telegram.sent == [
        (456, "Sesi Devin baru dibuat: https://app.devin.ai/sessions/created")
    ]


@pytest.mark.asyncio
async def test_followup_message_uses_existing_session(tmp_path) -> None:
    bot, telegram, devin = make_bot(tmp_path)

    await bot.handle_update(make_update("/session devin-existing"))
    await bot.handle_update(make_update("lanjutkan"))

    assert devin.sent_messages == [("devin-existing", "lanjutkan")]
    assert telegram.sent[-1] == (
        456,
        "Terkirim ke Devin: https://app.devin.ai/sessions/existing",
    )


@pytest.mark.asyncio
async def test_unauthorized_user_is_rejected(tmp_path) -> None:
    bot, telegram, devin = make_bot(tmp_path, allowed_user_ids="999")

    await bot.handle_update(make_update("halo", user_id=123))

    assert devin.created_prompts == []
    assert telegram.sent == [(456, "User Telegram ini belum diizinkan.")]
