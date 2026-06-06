from __future__ import annotations

import re
from dataclasses import dataclass

from rakiti_ai.config import ButlerConfig
from rakiti_ai.permissions import HIGH_RISK, LOW_RISK, MEDIUM_RISK, NO_RISK, get_action_args, normalize_action_name


LOW_RISK_ACTIONS = {
    "open_app",
    "open_url",
    "search_files",
    "create_folder",
    "show_system_info",
    "show_voice_devices",
    "create_note",
    "list_notes",
    "set_preference",
    "get_preference",
    "help",
}

MEDIUM_RISK_ACTIONS = {
    "move_file",
    "rename_file",
    "run_command",
}

HIGH_RISK_ACTIONS = {
    "delete_file",
    "delete_folder",
    "inspect_file_contents",
    "format_disk",
    "modify_registry",
    "change_firewall",
    "disable_security",
    "access_passwords",
    "read_passwords",
    "access_browser_cookies",
    "access_cookies",
    "access_sessions",
    "access_tokens",
    "access_ssh_keys",
    "access_crypto_wallets",
    "access_wallets",
    "access_keychain",
    "access_credentials",
    "read_private_keys",
    "send_email",
    "install_software",
    "install_service",
    "install_startup_task",
    "install_cron_job",
    "install_scheduled_task",
    "install_registry_autostart",
    "upload_files",
    "upload_file",
    "exfiltrate_data",
    "arbitrary_shell_command",
    "background_keylogging",
    "keylogging",
    "screenshot_capture",
    "microphone_recording",
    "background_recording",
    "webcam_access",
    "hidden_autostart",
    "persistence_without_permission",
}

ALLOWED_COMMANDS = {
    "pwd",
    "cd",
    "ls",
    "dir",
    "whoami",
    "python --version",
    "node --version",
    "git status",
    "git branch",
    "git log --oneline -5",
}

DANGEROUS_COMMAND_PATTERNS = (
    r"\brm\s+-rf\b",
    r"\bdel\s+/s\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\breg\s+delete\b",
    r"\bchmod\s+777\s+/",
    r"\bcurl\b.*\|\s*sh\b",
    r"\bwget\b.*\|\s*sh\b",
    r"\bmkfs\b",
    r"\bdiskpart\b",
    r"\bbcdedit\b",
    r"\bpowershell\b.*\bencodedcommand\b",
    r"\bencodedcommand\b",
    r"\bremove-item\b",
    r"\brmdir\b",
    r"\brd\s+/s\b",
)

SENSITIVE_REQUEST_PATTERNS = (
    r"\bpasswords?\b",
    r"\bpassphrases?\b",
    r"\bcredentials?\b",
    r"\bkeychain\b",
    r"\bcookies?\b",
    r"\bbrowser\s+session\b",
    r"\bprivate\s+key\b",
    r"\bssh\s+key\b",
    r"\bapi\s+key\b",
    r"\bauth\s+token\b",
    r"\bseed\s+phrase\b",
    r"\bwallet\b",
)

FILE_CONTENT_REQUEST_PATTERNS = (
    r"\bread\s+.*\bfile\b",
    r"\bshow\s+.*\bfile\b",
    r"\binspect\s+.*\bfile\b",
    r"\bfile\s+contents?\b",
    r"\bcat\s+",
)


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    risk: str
    requires_confirmation: bool = False
    reason: str = ""


def normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip()).lower()


def contains_dangerous_command(command: str) -> bool:
    normalized = normalize_command(command)
    return any(re.search(pattern, normalized) for pattern in DANGEROUS_COMMAND_PATTERNS)


def is_command_allowed(command: str) -> bool:
    normalized = normalize_command(command)
    return normalized in ALLOWED_COMMANDS and not contains_dangerous_command(normalized)


def contains_sensitive_request(text: str) -> bool:
    normalized = normalize_command(text)
    return any(re.search(pattern, normalized) for pattern in SENSITIVE_REQUEST_PATTERNS)


def contains_file_content_request(text: str) -> bool:
    normalized = normalize_command(text)
    return any(re.search(pattern, normalized) for pattern in FILE_CONTENT_REQUEST_PATTERNS)


class SafetyValidator:
    def __init__(self, config: ButlerConfig):
        self.config = config

    def validate(
        self,
        action: dict[str, object],
        *,
        user_command: str = "",
    ) -> SafetyDecision:
        action_name = normalize_action_name(action)
        args = get_action_args(action)

        if action_name == "clarify":
            return SafetyDecision(False, NO_RISK, reason=str(args.get("message", "Clarification needed.")))

        if action_name == "blocked":
            return SafetyDecision(False, HIGH_RISK, reason=str(args.get("reason", "This action is blocked.")))

        if user_command and contains_sensitive_request(user_command):
            return SafetyDecision(False, HIGH_RISK, reason="Requests involving secrets or credential stores are blocked.")

        if user_command and contains_file_content_request(user_command):
            return SafetyDecision(False, HIGH_RISK, reason="File content inspection is blocked in version 1.")

        if action_name in HIGH_RISK_ACTIONS:
            return SafetyDecision(False, HIGH_RISK, reason=f"{action_name} is blocked in version 1.")

        if action_name not in LOW_RISK_ACTIONS and action_name not in MEDIUM_RISK_ACTIONS:
            return SafetyDecision(False, HIGH_RISK, reason=f"Unknown or unapproved action: {action_name}")

        if action_name == "run_command":
            command = str(args.get("command", ""))
            if contains_dangerous_command(command):
                return SafetyDecision(False, HIGH_RISK, reason="Dangerous command string rejected.")
            if not is_command_allowed(command):
                return SafetyDecision(False, MEDIUM_RISK, reason="Command is not in the version-1 allowlist.")

        if action_name in MEDIUM_RISK_ACTIONS:
            return SafetyDecision(
                True,
                MEDIUM_RISK,
                requires_confirmation=self.config.require_confirmation_for_medium_risk,
            )

        return SafetyDecision(True, LOW_RISK)
