from __future__ import annotations

from rakiti_ai.app_allowlist import app_command_for_os, canonicalize_app_name
from rakiti_ai.config import ButlerConfig
from rakiti_ai.os_adapters import get_adapter


UNAPPROVED_APP_MESSAGE = "That app is not approved yet. Add it to config first."


def open_app(app_name: str, config: ButlerConfig) -> str:
    canonical_name = canonicalize_app_name(app_name, config.allowed_apps)
    if not canonical_name:
        raise ValueError(UNAPPROVED_APP_MESSAGE)

    command = app_command_for_os(canonical_name, config.allowed_apps, config.os_name)
    if not command:
        raise ValueError(f"No app command configured for {canonical_name} on {config.os_name}.")

    adapter = get_adapter(config.os_name)
    adapter.open_app_command(command)
    return f"Opened app: {canonical_name}"
