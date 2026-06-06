from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class LocalStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.session() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS actions_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_command TEXT NOT NULL,
                    original_command TEXT,
                    input_mode TEXT NOT NULL DEFAULT 'text',
                    transcript TEXT,
                    transcript_confidence REAL,
                    parser_used TEXT NOT NULL DEFAULT 'rule_based',
                    llm_raw_output TEXT,
                    confidence REAL,
                    parsed_action TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
                """
            )
            self._ensure_actions_log_columns(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _ensure_actions_log_columns(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute("PRAGMA table_info(actions_log)").fetchall()
        existing_columns = {str(row["name"]) for row in rows}
        if "input_mode" not in existing_columns:
            connection.execute("ALTER TABLE actions_log ADD COLUMN input_mode TEXT NOT NULL DEFAULT 'text'")
        if "original_command" not in existing_columns:
            connection.execute("ALTER TABLE actions_log ADD COLUMN original_command TEXT")
        if "transcript" not in existing_columns:
            connection.execute("ALTER TABLE actions_log ADD COLUMN transcript TEXT")
        if "transcript_confidence" not in existing_columns:
            connection.execute("ALTER TABLE actions_log ADD COLUMN transcript_confidence REAL")
        if "parser_used" not in existing_columns:
            connection.execute("ALTER TABLE actions_log ADD COLUMN parser_used TEXT NOT NULL DEFAULT 'rule_based'")
        if "llm_raw_output" not in existing_columns:
            connection.execute("ALTER TABLE actions_log ADD COLUMN llm_raw_output TEXT")
        if "confidence" not in existing_columns:
            connection.execute("ALTER TABLE actions_log ADD COLUMN confidence REAL")

    def count_actions(self) -> int:
        with self.session() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM actions_log").fetchone()
        return int(row["count"])

    def create_note(self, title: str, body: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO notes (title, body, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (title, body, now, now),
            )
            return int(cursor.lastrowid)

    def list_notes(self, limit: int = 20) -> list[dict[str, object]]:
        with self.session() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM notes
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_preference(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.session() as connection:
            connection.execute(
                """
                INSERT INTO preferences (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def get_preference(self, key: str) -> dict[str, object] | None:
        with self.session() as connection:
            row = connection.execute(
                "SELECT key, value, updated_at FROM preferences WHERE key = ?",
                (key,),
            ).fetchone()
        return dict(row) if row else None
