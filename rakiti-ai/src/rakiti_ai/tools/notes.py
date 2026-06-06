from __future__ import annotations

from rakiti_ai.memory import LocalStore
from rakiti_ai.privacy import reject_sensitive_text


def create_note(title: str, body: str, store: LocalStore) -> str:
    clean_title = title.strip()
    clean_body = body.strip()
    if not clean_title:
        raise ValueError("Note title cannot be empty.")
    if not clean_body:
        raise ValueError("Note body cannot be empty.")
    reject_sensitive_text(f"{clean_title}\n{clean_body}", context="Note")
    note_id = store.create_note(clean_title, clean_body)
    return f"Created note {note_id}: {clean_title}. Do not store passwords, tokens, or private keys in notes."


def list_notes(store: LocalStore, limit: int = 20) -> list[dict[str, object]]:
    return store.list_notes(limit=limit)
