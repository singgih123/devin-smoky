from app.store import SessionStore


def test_session_store_persists_chat_session(tmp_path) -> None:
    store = SessionStore(tmp_path / "bot.db")

    assert store.get_session(1) is None

    store.set_session(1, "devin-one")
    assert store.get_session(1) == "devin-one"

    store.set_session(1, "devin-two")
    assert store.get_session(1) == "devin-two"
