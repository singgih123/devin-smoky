from __future__ import annotations

import sqlite3
from pathlib import Path


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    chat_id INTEGER PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get_session(self, chat_id: int) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM chat_sessions WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        if row is None:
            return None
        value = row[0]
        return value if isinstance(value, str) else None

    def set_session(self, chat_id: int, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO chat_sessions (chat_id, session_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, session_id),
            )
