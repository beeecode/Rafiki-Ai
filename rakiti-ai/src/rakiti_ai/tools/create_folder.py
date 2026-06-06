from __future__ import annotations

from rakiti_ai.config import ButlerConfig
from rakiti_ai.permissions import require_allowed_path


def create_folder(path: str, config: ButlerConfig) -> str:
    folder_path = require_allowed_path(path, config)
    folder_path.mkdir(parents=True, exist_ok=True)
    return f"Created folder: {folder_path}"
