from __future__ import annotations

from rakiti_ai.memory import LocalStore
from rakiti_ai.privacy import reject_sensitive_text


def set_preference(key: str, value: str, store: LocalStore) -> str:
    clean_key = key.strip().casefold().replace(" ", "_")
    clean_value = value.strip()
    if not clean_key:
        raise ValueError("Preference key cannot be empty.")
    if not clean_value:
        raise ValueError("Preference value cannot be empty.")
    reject_sensitive_text(f"{clean_key}\n{clean_value}", context="Preference")
    store.set_preference(clean_key, clean_value)
    return f"Saved preference: {clean_key}"


def get_preference(key: str, store: LocalStore) -> str:
    clean_key = key.strip().casefold().replace(" ", "_")
    if not clean_key:
        raise ValueError("Preference key cannot be empty.")
    preference = store.get_preference(clean_key)
    if not preference:
        return f"No preference saved for: {clean_key}"
    return f"{preference['key']}: {preference['value']}"
