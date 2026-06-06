from __future__ import annotations

import re
from typing import Any


def normalize_app_alias(value: str) -> str:
    lowered = value.strip().casefold()
    lowered = re.sub(r"[_-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered)


def canonicalize_app_name(
    requested_name: str,
    allowed_apps: dict[str, dict[str, Any]],
) -> str | None:
    requested = normalize_app_alias(requested_name)
    for canonical_name, app_config in allowed_apps.items():
        names = {canonical_name}
        aliases = app_config.get("aliases", [])
        if isinstance(aliases, list):
            names.update(str(alias) for alias in aliases)
        if requested in {normalize_app_alias(name) for name in names}:
            return canonical_name
    return None


def app_command_for_os(
    canonical_name: str,
    allowed_apps: dict[str, dict[str, Any]],
    os_name: str,
) -> str | None:
    app_config = allowed_apps.get(canonical_name)
    if not app_config:
        return None
    command = app_config.get(os_name)
    if isinstance(command, str) and command.strip():
        return command.strip()
    return None
