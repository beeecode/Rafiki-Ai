from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rakiti_ai.config import ButlerConfig
from rakiti_ai.memory import LocalStore
from rakiti_ai.permissions import get_action_args, normalize_action_name
from rakiti_ai.safety import SafetyDecision, SafetyValidator
from rakiti_ai.tools.create_folder import create_folder
from rakiti_ai.tools.file_search import search_files
from rakiti_ai.tools.help import show_help
from rakiti_ai.tools.move_file import move_file
from rakiti_ai.tools.notes import create_note, list_notes
from rakiti_ai.tools.open_app import open_app
from rakiti_ai.tools.open_url import open_url
from rakiti_ai.tools.preferences import get_preference, set_preference
from rakiti_ai.tools.rename_file import rename_file
from rakiti_ai.tools.run_command import run_command
from rakiti_ai.tools.system_info import show_system_info
from rakiti_ai.voice import get_voice_device_report


@dataclass(frozen=True)
class ActionResult:
    success: bool
    status: str
    output: Any = None
    error_message: str | None = None
    risk_level: str = "none"


class ActionRouter:
    def __init__(
        self,
        config: ButlerConfig,
        safety: SafetyValidator | None = None,
        store: LocalStore | None = None,
    ):
        self.config = config
        self.safety = safety or SafetyValidator(config)
        self.store = store or LocalStore(config.data_dir / "rakiti_ai.sqlite3")

    def check_safety(
        self,
        action: dict[str, object],
        *,
        user_command: str = "",
    ) -> SafetyDecision:
        return self.safety.validate(action, user_command=user_command)

    def execute(
        self,
        action: dict[str, object],
        *,
        user_command: str = "",
        confirmed: bool = False,
    ) -> ActionResult:
        decision = self.check_safety(action, user_command=user_command)
        if not decision.allowed:
            return ActionResult(
                success=False,
                status="blocked",
                error_message=decision.reason,
                risk_level=decision.risk,
            )
        if decision.requires_confirmation and not confirmed:
            return ActionResult(
                success=False,
                status="requires_confirmation",
                error_message="Confirmation required.",
                risk_level=decision.risk,
            )

        action_name = normalize_action_name(action)
        args = get_action_args(action)

        try:
            output = self._execute_allowed(action_name, args)
            return ActionResult(
                success=True,
                status="success",
                output=output,
                risk_level=decision.risk,
            )
        except Exception as exc:
            return ActionResult(
                success=False,
                status="failure",
                error_message=str(exc),
                risk_level=decision.risk,
            )

    def _execute_allowed(self, action_name: str, args: dict[str, object]) -> Any:
        if action_name == "open_app":
            return open_app(str(args.get("app_name", "")), self.config)
        if action_name == "open_url":
            return open_url(str(args.get("url", "")))
        if action_name == "search_files":
            return search_files(str(args.get("query", "")), self.config)
        if action_name == "create_folder":
            return create_folder(str(args.get("path", "")), self.config)
        if action_name == "move_file":
            return move_file(str(args.get("source", "")), str(args.get("destination", "")), self.config)
        if action_name == "rename_file":
            return rename_file(str(args.get("source", "")), str(args.get("destination", "")), self.config)
        if action_name == "show_system_info":
            return show_system_info(self.config.os_name)
        if action_name == "show_voice_devices":
            return get_voice_device_report()
        if action_name == "create_note":
            return create_note(str(args.get("title", "")), str(args.get("body", "")), self.store)
        if action_name == "list_notes":
            return list_notes(self.store, limit=int(args.get("limit", 20) or 20))
        if action_name == "set_preference":
            return set_preference(str(args.get("key", "")), str(args.get("value", "")), self.store)
        if action_name == "get_preference":
            return get_preference(str(args.get("key", "")), self.store)
        if action_name == "help":
            return show_help()
        if action_name == "run_command":
            return run_command(str(args.get("command", "")))
        raise ValueError(f"No route for action: {action_name}")
