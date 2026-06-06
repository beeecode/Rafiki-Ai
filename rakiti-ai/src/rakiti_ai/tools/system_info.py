from __future__ import annotations

import platform
import sys
from pathlib import Path

from rakiti_ai import __version__


def show_system_info(os_name: str) -> dict[str, str]:
    return {
        "detected_os": os_name,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "current_directory": str(Path.cwd()),
        "app_version": __version__,
    }
