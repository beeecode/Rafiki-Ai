from __future__ import annotations

import os
from pathlib import Path

from rakiti_ai.config import ButlerConfig
from rakiti_ai.permissions import is_blocked_path, is_allowed_path


def search_files(query: str, config: ButlerConfig) -> list[dict[str, str]]:
    normalized_query = query.casefold().strip()
    if not normalized_query:
        raise ValueError("Search query cannot be empty.")

    results: list[dict[str, str]] = []
    for allowed_dir in config.allowed_directories:
        if not allowed_dir.exists() or is_blocked_path(allowed_dir, config):
            continue
        for root, dirs, files in os.walk(allowed_dir, followlinks=False):
            root_path = Path(root)
            dirs[:] = [
                dirname
                for dirname in dirs
                if not is_blocked_path(root_path / dirname, config)
            ]
            for filename in files:
                file_path = root_path / filename
                if not is_allowed_path(file_path, config):
                    continue
                if normalized_query in filename.casefold():
                    results.append({"name": filename, "path": str(file_path)})
                    if len(results) >= config.max_search_results:
                        return results
    return results
