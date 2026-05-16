from app.devin_client import (
    extract_message_items,
    extract_session_id,
    format_recent_messages,
    normalize_session_id,
    session_web_url,
)


def test_normalize_session_id_adds_prefix() -> None:
    assert normalize_session_id("abc123") == "devin-abc123"
    assert normalize_session_id("devin-abc123") == "devin-abc123"


def test_session_web_url_removes_api_prefix() -> None:
    assert session_web_url("devin-abc123") == "https://app.devin.ai/sessions/abc123"


def test_extract_session_id_accepts_nested_session() -> None:
    assert extract_session_id({"session": {"id": "abc123"}}) == "devin-abc123"


def test_format_recent_messages_handles_common_shapes() -> None:
    data = {
        "messages": [
            {"role": "user", "message": "halo"},
            {"role": "assistant", "content": "siap"},
        ]
    }

    assert extract_message_items(data) == data["messages"]
    assert format_recent_messages(data) == "user: halo\n\nassistant: siap"
