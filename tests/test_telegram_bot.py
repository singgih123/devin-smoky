import asyncio
from pathlib import Path

import pytest
from app.config import Settings
from app.store import SessionStore
from app.telegram_bot import (
    BotService,
    extract_new_devin_response,
    extract_telegram_message,
    split_telegram_message,
)
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
        self.message_responses: list[JSONObject] = []

    async def create_session(self, prompt: str) -> str:
        self.created_prompts.append(prompt)
        return "devin-created"

    async def send_message(self, session_id: str, message: str) -> None:
        self.sent_messages.append((session_id, message))

    async def list_messages(self, session_id: str) -> JSONObject:
        if self.message_responses:
            return self.message_responses.pop(0)
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
    response_poll_attempts: int = 0,
    response_poll_interval_seconds: float = 0.0,
) -> tuple[BotService, FakeTelegram, FakeDevin]:
    settings = Settings(
        _env_file=None,
        telegram_allowed_user_ids=allowed_user_ids,
        data_dir=tmp_path,
        devin_response_poll_attempts=response_poll_attempts,
        devin_response_poll_interval_seconds=response_poll_interval_seconds,
    )
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


def test_extract_new_devin_response_ignores_known_events() -> None:
    data: JSONObject = {
        "items": [
            {"source": "devin", "event_id": "old", "message": "jawaban lama"},
            {"source": "user", "event_id": "user-1", "message": "lanjut"},
            {"source": "devin", "event_id": "new", "message": "jawaban baru"},
        ]
    }

    assert extract_new_devin_response(data, {"old"}) == "jawaban baru"


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
async def test_followup_message_relays_new_devin_response(tmp_path) -> None:
    bot, telegram, devin = make_bot(tmp_path, response_poll_attempts=1)
    devin.message_responses = [
        {"items": [{"source": "devin", "event_id": "old", "message": "jawaban lama"}]},
        {
            "items": [
                {"source": "devin", "event_id": "old", "message": "jawaban lama"},
                {"source": "user", "event_id": "user-1", "message": "lanjutkan"},
                {"source": "devin", "event_id": "new", "message": "jawaban baru"},
            ]
        },
    ]

    await bot.handle_update(make_update("/session devin-existing"))
    await bot.handle_update(make_update("lanjutkan"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert telegram.sent[-1] == (456, "jawaban baru")


@pytest.mark.asyncio
async def test_unauthorized_user_is_rejected(tmp_path) -> None:
    bot, telegram, devin = make_bot(tmp_path, allowed_user_ids="999")

    await bot.handle_update(make_update("halo", user_id=123))

    assert devin.created_prompts == []
    assert telegram.sent == [(456, "User Telegram ini belum diizinkan.")]
