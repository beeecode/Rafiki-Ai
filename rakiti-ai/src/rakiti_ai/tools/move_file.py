from __future__ import annotations

import shutil

from rakiti_ai.config import ButlerConfig
from rakiti_ai.permissions import require_allowed_path


def move_file(source: str, destination: str, config: ButlerConfig) -> str:
    source_path = require_allowed_path(source, config, must_exist=True)
    destination_path = require_allowed_path(destination, config)

    if not source_path.is_file():
        raise ValueError(f"Source is not a file: {source_path}")
    if destination_path.exists():
        raise FileExistsError(f"Destination already exists: {destination_path}")
    if not destination_path.parent.exists():
        raise FileNotFoundError(f"Destination folder does not exist: {destination_path.parent}")

    shutil.move(str(source_path), str(destination_path))
    return f"Moved file to: {destination_path}"
