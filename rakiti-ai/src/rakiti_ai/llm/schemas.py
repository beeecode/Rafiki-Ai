from __future__ import annotations

ALLOWED_LLM_ACTIONS = {
    "open_app",
    "open_url",
    "search_files",
    "create_folder",
    "move_file",
    "rename_file",
    "show_system_info",
    "run_command",
    "create_note",
    "list_notes",
    "set_preference",
    "get_preference",
    "help",
    "unclear",
    "blocked",
}

ALLOWED_RISKS = {"low", "medium", "high"}

ALLOWED_ARGS_BY_ACTION: dict[str, set[str]] = {
    "open_app": {"app_name"},
    "open_url": {"url"},
    "search_files": {"query"},
    "create_folder": {"path"},
    "move_file": {"source", "destination"},
    "rename_file": {"source", "destination"},
    "show_system_info": set(),
    "run_command": {"command"},
    "create_note": {"title", "body"},
    "list_notes": {"limit"},
    "set_preference": {"key", "value"},
    "get_preference": {"key"},
    "help": set(),
    "unclear": set(),
    "blocked": set(),
}

REQUIRED_ARGS_BY_ACTION: dict[str, set[str]] = {
    "open_app": {"app_name"},
    "open_url": {"url"},
    "search_files": {"query"},
    "create_folder": {"path"},
    "move_file": {"source", "destination"},
    "rename_file": {"source", "destination"},
    "show_system_info": set(),
    "run_command": {"command"},
    "create_note": {"title", "body"},
    "list_notes": set(),
    "set_preference": {"key", "value"},
    "get_preference": {"key"},
    "help": set(),
    "unclear": set(),
    "blocked": set(),
}

LOW_RISK_ACTIONS = {
    "open_app",
    "open_url",
    "search_files",
    "create_folder",
    "show_system_info",
    "create_note",
    "list_notes",
    "set_preference",
    "get_preference",
    "help",
}
MEDIUM_RISK_ACTIONS = {"move_file", "rename_file", "run_command"}

REQUIRED_FIELDS = {"action", "args", "risk", "confidence", "reason"}
