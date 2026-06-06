from __future__ import annotations

import re
import shlex
from typing import Any
from urllib.parse import urlparse

from rakiti_ai.app_allowlist import canonicalize_app_name
from rakiti_ai.permissions import HIGH_RISK, LOW_RISK, MEDIUM_RISK, NO_RISK
from rakiti_ai.tools.open_app import UNAPPROVED_APP_MESSAGE


HELP_MESSAGE = """Hi, I am Rafiki AI. I can help with local, approved laptop tasks.

Try:
- open chrome
- open https://example.com
- search files for invoice
- create folder Projects/TestApp
- create note Shopping: buy tea
- list notes
- show system info
- run command pwd

Medium-risk actions like move, rename, and run command require exact CONFIRM."""


HIGH_RISK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bdelete\b|\bremove\b|\berase\b|\bunlink\b", "Deleting files or folders is blocked in version 1."),
    (r"\bformat\b|\bmkfs\b|\bdiskpart\b", "Disk formatting is blocked."),
    (r"\bregistry\b|\breg\s+delete\b", "Registry modification is blocked."),
    (r"\bfirewall\b|\bdefender\b|\bantivirus\b|\bgatekeeper\b|\bsip\b", "Changing security tools is blocked."),
    (r"\bpasswords?\b|\bpassphrases?\b|\bcredentials?\b|\bkeychain\b", "Credential access is blocked."),
    (r"\bcookie\b|\bbrowser\s+session\b|\bsession\s+token\b", "Browser cookie/session access is blocked."),
    (r"\bprivate\s+key\b|\bssh\s+key\b|\bapi\s+key\b|\bauth\s+token\b|\btoken\b", "Secret/key access is blocked."),
    (r"\bseed\s+phrase\b|\bwallet\b|\bcrypto\b", "Wallet or seed phrase access is blocked."),
    (r"\bfile\s+contents?\b|\bread\s+.*\bfile\b|\binspect\s+.*\bfile\b|\bshow\s+.*\bfile\b|\bcat\s+", "File content inspection is blocked."),
    (r"\bsend\s+email\b|\bemail\s+.*\bto\b", "Sending email is blocked."),
    (r"\binstall\b|\bdownload\s+and\s+run\b", "Installing or auto-running software is blocked."),
    (r"\bupload\b|\bexfiltrate\b|\bexport\b", "Uploading or exfiltrating data is blocked."),
    (r"\bkeylog\b|\bkeylogging\b", "Keylogging is blocked."),
    (r"\bscreenshot\b|\bscreen\s+capture\b", "Screenshot capture is blocked."),
    (r"\bmicrophone\b|\brecord\s+audio\b", "Microphone recording is blocked."),
    (r"\bwebcam\b|\bcamera\b", "Webcam access is blocked."),
    (r"\bautostart\b|\bstartup\b|\bpersistence\b|\bdaemon\b|\bservice\b|\bcron\b|\bscheduled\s+task\b", "Hidden persistence is blocked."),
)


def _action(action_name: str, args: dict[str, object], risk: str) -> dict[str, object]:
    return {"action": action_name, "args": args, "risk": risk}


def _clarify(message: str) -> dict[str, object]:
    return _action("clarify", {"message": message}, NO_RISK)


def _blocked(reason: str) -> dict[str, object]:
    return _action("blocked", {"reason": reason}, HIGH_RISK)


def _split_args(text: str) -> list[str]:
    try:
        parts = shlex.split(text, posix=False)
    except ValueError:
        return []
    return [part.strip("\"'") for part in parts if part.strip("\"'")]


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class IntentParser:
    """Small conservative parser for version-1 commands."""

    def __init__(self, allowed_apps: dict[str, dict[str, Any]] | None = None):
        self.allowed_apps = allowed_apps or _default_allowed_apps()

    def parse(self, user_command: str) -> dict[str, object]:
        original = user_command.strip()
        command = _normalize_polite_command(re.sub(r"\s+", " ", original))
        lower_command = command.lower()

        if not command:
            return _clarify("Please type a command.")

        if lower_command in {"hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening"}:
            return _clarify(HELP_MESSAGE)

        if lower_command in {"help", "?", "commands", "what can you do", "show help"}:
            return _action("help", {}, LOW_RISK)

        for pattern, reason in HIGH_RISK_PATTERNS:
            if re.search(pattern, lower_command):
                return _blocked(reason)

        app_match = re.match(r"^(open|launch|start)\s+(.+)$", lower_command)
        if app_match:
            verb = app_match.group(1)
            target = command[len(verb) + 1 :].strip()
            if not target:
                return _clarify("Tell me what app or URL to open.")
            if _is_http_url(target):
                return _action("open_url", {"url": target}, LOW_RISK)
            if "://" in target:
                return _blocked("Only http:// and https:// URLs are allowed.")
            canonical_name = canonicalize_app_name(target, self.allowed_apps)
            if not canonical_name:
                return _clarify(UNAPPROVED_APP_MESSAGE)
            return _action("open_app", {"app_name": canonical_name}, LOW_RISK)

        if lower_command.startswith("search files for "):
            query = command[len("search files for ") :].strip()
            if not query:
                return _clarify("Tell me what filename text to search for.")
            return _action("search_files", {"query": query}, LOW_RISK)

        find_match = re.match(r"^(find|search for)\s+(.+?)\s+files?$", lower_command)
        if find_match:
            query = command[command.lower().find(find_match.group(2)) :].rsplit(" ", 1)[0].strip()
            if not query:
                return _clarify("Tell me what filename text to search for.")
            return _action("search_files", {"query": query}, LOW_RISK)

        if lower_command.startswith("find files for "):
            query = command[len("find files for ") :].strip()
            if not query:
                return _clarify("Tell me what filename text to search for.")
            return _action("search_files", {"query": query}, LOW_RISK)

        if lower_command.startswith("create folder "):
            path = command[len("create folder ") :].strip()
            if not path:
                return _clarify("Tell me what folder path to create.")
            return _action("create_folder", {"path": path}, LOW_RISK)

        folder_match = re.match(r"^create (a )?folder (called|named)\s+(.+)$", lower_command)
        if folder_match:
            folder_name = command[command.lower().find(folder_match.group(3)) :].strip()
            if not folder_name:
                return _clarify("Tell me what folder path to create.")
            return _action("create_folder", {"path": f"Projects/{folder_name}"}, LOW_RISK)

        if lower_command.startswith("mkdir "):
            path = command[len("mkdir ") :].strip()
            if not path:
                return _clarify("Tell me what folder path to create.")
            return _action("create_folder", {"path": path}, LOW_RISK)

        if lower_command.startswith("move file "):
            remainder = command[len("move file ") :].strip()
            source, destination = self._parse_two_paths(remainder)
            if not source or not destination:
                return _clarify("Use: move file <source> <destination>.")
            return _action(
                "move_file",
                {"source": source, "destination": destination},
                MEDIUM_RISK,
            )

        if lower_command.startswith("rename file "):
            remainder = command[len("rename file ") :].strip()
            source, destination = self._parse_two_paths(remainder)
            if not source or not destination:
                return _clarify("Use: rename file <source> <destination>.")
            return _action(
                "rename_file",
                {"source": source, "destination": destination},
                MEDIUM_RISK,
            )

        if lower_command in {"show system info", "system info", "show info"}:
            return _action("show_system_info", {}, LOW_RISK)

        if lower_command in {
            "voice devices",
            "microphone devices",
            "mic devices",
            "show voice devices",
            "show microphone devices",
            "show microphones",
        }:
            return _action("show_voice_devices", {}, LOW_RISK)

        if lower_command in {"list notes", "show notes", "my notes"}:
            return _action("list_notes", {}, LOW_RISK)

        note_match = re.match(r"^(create note|add note|note)\s+(.+)$", command, re.IGNORECASE)
        if note_match:
            note_text = note_match.group(2).strip()
            if ":" in note_text:
                title, body = note_text.split(":", 1)
            elif " about " in note_text.casefold():
                title, body = re.split(r"\s+about\s+", note_text, maxsplit=1, flags=re.IGNORECASE)
            else:
                return _clarify("Use: create note <title>: <body>.")
            return _action("create_note", {"title": title.strip(), "body": body.strip()}, LOW_RISK)

        set_pref_match = re.match(r"^set preference\s+(.+?)\s+to\s+(.+)$", command, re.IGNORECASE)
        if set_pref_match:
            return _action(
                "set_preference",
                {"key": set_pref_match.group(1).strip(), "value": set_pref_match.group(2).strip()},
                LOW_RISK,
            )

        get_pref_match = re.match(r"^(get|show)\s+preference\s+(.+)$", command, re.IGNORECASE)
        if get_pref_match:
            return _action("get_preference", {"key": get_pref_match.group(2).strip()}, LOW_RISK)

        if lower_command.startswith("run command "):
            command_text = command[len("run command ") :].strip()
            if not command_text:
                return _clarify("Tell me which allowlisted command to run.")
            return _action("run_command", {"command": command_text}, MEDIUM_RISK)

        return _clarify("I did not understand that. Try a supported command.")

    def _parse_two_paths(self, text: str) -> tuple[str | None, str | None]:
        if " to " in text:
            source, destination = text.split(" to ", 1)
            return source.strip(), destination.strip()

        parts = _split_args(text)
        if len(parts) == 2:
            return parts[0], parts[1]
        return None, None


def _default_allowed_apps() -> dict[str, dict[str, Any]]:
    return {
        "chrome": {"aliases": ["chrome", "google chrome", "google", "browser"]},
        "vscode": {"aliases": ["vscode", "vs code", "visual studio code", "code", "code editor"]},
        "notepad": {"aliases": ["notepad", "text editor"]},
        "file_explorer": {"aliases": ["file explorer", "explorer", "files"]},
        "calculator": {"aliases": ["calculator", "calc"]},
        "terminal": {"aliases": ["terminal", "powershell", "shell"]},
    }


def _normalize_polite_command(command: str) -> str:
    cleaned = command.strip().strip("?!.")
    cleaned = re.sub(r"^(please\s+)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(can|could|would)\s+you\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+for\s+me$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()
