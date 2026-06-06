from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from rakiti_ai.memory import LocalStore


SENSITIVE_VALUE_PATTERNS = (
    r"(?i)\b(passwords?|passphrases?|secrets?|tokens?|api[_ -]?keys?|private[_ -]?keys?|ssh[_ -]?keys?|seed[_ -]?phrases?|cookies?|wallets?|keychains?|credentials?)\b\s*[:=]\s*[^,\s\"'}]+",
    r"(?i)\b(passwords?|passphrases?|secrets?|tokens?|api[_ -]?keys?|private[_ -]?keys?|ssh[_ -]?keys?|seed[_ -]?phrases?|cookies?|wallets?|keychains?|credentials?)\b\s+[^,\s\"'}]+",
)


def redact_sensitive(value: str) -> str:
    redacted = value
    for pattern in SENSITIVE_VALUE_PATTERNS:
        redacted = re.sub(pattern, lambda match: match.group(1) + " [REDACTED]", redacted)
    return redacted


def _safe_json(data: dict[str, object]) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    return redact_sensitive(raw)


class ActionLogger:
    def __init__(self, store: LocalStore):
        self.store = store

    def log_action(
        self,
        *,
        user_command: str,
        parsed_action: dict[str, object],
        risk_level: str,
        status: str,
        error_message: str | None = None,
        input_mode: str = "text",
        transcript: str | None = None,
        transcript_confidence: float | None = None,
        parser_used: str = "rule_based",
        llm_raw_output: str | None = None,
        confidence: float | None = None,
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.store.session() as connection:
            connection.execute(
                """
                INSERT INTO actions_log (
                    timestamp,
                    user_command,
                    original_command,
                    input_mode,
                    transcript,
                    transcript_confidence,
                    parser_used,
                    llm_raw_output,
                    confidence,
                    parsed_action,
                    risk_level,
                    status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    redact_sensitive(user_command),
                    redact_sensitive(user_command),
                    input_mode,
                    redact_sensitive(transcript or "") or None,
                    transcript_confidence,
                    parser_used,
                    redact_sensitive(llm_raw_output or "") or None,
                    confidence,
                    _safe_json(parsed_action),
                    risk_level,
                    status,
                    redact_sensitive(error_message or "") or None,
                ),
            )

    def recent_actions(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.store.session() as connection:
            rows = connection.execute(
                """
                SELECT id, timestamp, user_command, original_command, input_mode, transcript, transcript_confidence,
                       parser_used, llm_raw_output, confidence,
                       parsed_action, risk_level, status, error_message
                FROM actions_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
