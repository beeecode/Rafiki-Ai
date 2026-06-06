from __future__ import annotations

from pathlib import Path

from rakiti_ai.config import ButlerConfig


LOW_RISK = "low"
MEDIUM_RISK = "medium"
HIGH_RISK = "high"
NO_RISK = "none"


def normalize_action_name(action: dict[str, object]) -> str:
    value = action.get("action", "")
    return str(value).strip().lower()


def get_action_args(action: dict[str, object]) -> dict[str, object]:
    args = action.get("args", {})
    if isinstance(args, dict):
        return args
    return {}


def resolve_user_path(raw_path: str, config: ButlerConfig) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = config.home_dir / candidate
    return candidate.resolve(strict=False)


def is_path_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def is_blocked_path(path: Path, config: ButlerConfig) -> bool:
    resolved = path.resolve(strict=False)
    return any(is_path_within(resolved, blocked) for blocked in config.blocked_directories)


def is_allowed_path(path: Path, config: ButlerConfig) -> bool:
    resolved = path.resolve(strict=False)
    if is_blocked_path(resolved, config):
        return False
    return any(is_path_within(resolved, allowed) for allowed in config.allowed_directories)


def require_allowed_path(
    raw_path: str,
    config: ButlerConfig,
    *,
    must_exist: bool = False,
) -> Path:
    path = resolve_user_path(raw_path, config)
    if must_exist and not path.exists():
        raise PermissionError(f"Path does not exist: {path}")
    if not is_allowed_path(path, config):
        raise PermissionError(f"Path is outside approved user directories: {path}")
    return path


def summarize_action(action: dict[str, object]) -> str:
    action_name = normalize_action_name(action)
    args = get_action_args(action)

    if action_name == "move_file":
        return f"Move file from {args.get('source')} to {args.get('destination')}"
    if action_name == "rename_file":
        return f"Rename file from {args.get('source')} to {args.get('destination')}"
    if action_name == "run_command":
        return f"Run allowed command: {args.get('command')}"
    if action_name == "create_folder":
        return f"Create folder: {args.get('path')}"
    if action_name == "open_url":
        return f"Open URL: {args.get('url')}"
    if action_name == "open_app":
        return f"Open app: {args.get('app_name')}"
    if action_name == "search_files":
        return f"Search filenames for: {args.get('query')}"
    if action_name == "show_system_info":
        return "Show basic system information"
    if action_name == "show_voice_devices":
        return "Show local microphone input devices"
    if action_name == "create_note":
        return f"Create local note: {args.get('title')}"
    if action_name == "list_notes":
        return "List local note titles"
    if action_name == "set_preference":
        return f"Set local preference: {args.get('key')}"
    if action_name == "get_preference":
        return f"Get local preference: {args.get('key')}"
    if action_name == "help":
        return "Show supported commands and safety rules"
    return action_name or "Unknown action"
