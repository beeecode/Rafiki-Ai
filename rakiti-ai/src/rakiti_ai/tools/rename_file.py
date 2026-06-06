from __future__ import annotations

from rakiti_ai.config import ButlerConfig
from rakiti_ai.permissions import require_allowed_path


def rename_file(source: str, destination: str, config: ButlerConfig) -> str:
    source_path = require_allowed_path(source, config, must_exist=True)
    destination_path = require_allowed_path(destination, config)

    if not source_path.is_file():
        raise ValueError(f"Source is not a file: {source_path}")
    if destination_path.exists():
        raise FileExistsError(f"Destination already exists: {destination_path}")
    if source_path.parent != destination_path.parent and not destination_path.parent.exists():
        raise FileNotFoundError(f"Destination folder does not exist: {destination_path.parent}")

    source_path.rename(destination_path)
    return f"Renamed file to: {destination_path}"
