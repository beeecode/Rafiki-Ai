from __future__ import annotations

from types import ModuleType

from rakiti_ai.os_adapters import linux, macos, windows


def get_adapter(os_name: str) -> ModuleType:
    if os_name == "windows":
        return windows
    if os_name == "macos":
        return macos
    if os_name == "linux":
        return linux
    return linux
