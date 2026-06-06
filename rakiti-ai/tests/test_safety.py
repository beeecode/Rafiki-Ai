from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rakiti_ai.config import ButlerConfig, VoiceConfig
from rakiti_ai.safety import (
    SafetyValidator,
    contains_dangerous_command,
    contains_file_content_request,
    is_command_allowed,
)


def make_config(root: Path) -> ButlerConfig:
    return ButlerConfig(
        project_root=root,
        home_dir=root,
        os_name="windows",
        allowed_apps={"chrome": {"windows": "chrome"}},
        allowed_directories=[root],
        blocked_directories=[root / ".ssh"],
        max_search_results=10,
        require_confirmation_for_medium_risk=True,
        data_dir=root / "data",
        logs_dir=root / "logs",
        voice=VoiceConfig(
            enabled=True,
            model_path="models/test",
            input_device=None,
            sample_rate=16000,
            max_duration_seconds=1,
            silence_timeout_seconds=0.5,
            silence_rms_threshold=500,
            low_confidence_threshold=0.72,
        ),
    )


class SafetyTests(unittest.TestCase):
    def test_safe_action_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            decision = validator.validate({"action": "create_folder", "args": {"path": "Projects"}, "risk": "low"})
            self.assertTrue(decision.allowed)
            self.assertEqual(decision.risk, "low")
            self.assertFalse(decision.requires_confirmation)

    def test_voice_device_diagnostic_is_low_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            decision = validator.validate({"action": "show_voice_devices", "args": {}, "risk": "low"})
            self.assertTrue(decision.allowed)
            self.assertEqual(decision.risk, "low")

    def test_new_low_risk_actions_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            for action in (
                {"action": "create_note", "args": {"title": "A", "body": "B"}, "risk": "low"},
                {"action": "list_notes", "args": {}, "risk": "low"},
                {"action": "set_preference", "args": {"key": "editor", "value": "vscode"}, "risk": "low"},
                {"action": "get_preference", "args": {"key": "editor"}, "risk": "low"},
                {"action": "help", "args": {}, "risk": "low"},
            ):
                decision = validator.validate(action)
                self.assertTrue(decision.allowed, action)
                self.assertEqual(decision.risk, "low")

    def test_medium_risk_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            decision = validator.validate(
                {
                    "action": "rename_file",
                    "args": {"source": "old.txt", "destination": "new.txt"},
                    "risk": "medium",
                }
            )
            self.assertTrue(decision.allowed)
            self.assertEqual(decision.risk, "medium")
            self.assertTrue(decision.requires_confirmation)

    def test_high_risk_action_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            decision = validator.validate({"action": "delete_file", "args": {"path": "old.txt"}, "risk": "high"})
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.risk, "high")

    def test_dangerous_command_strings_are_rejected(self) -> None:
        self.assertTrue(contains_dangerous_command("rm -rf /"))
        self.assertTrue(contains_dangerous_command("powershell EncodedCommand abc"))
        self.assertFalse(is_command_allowed("rm -rf /"))

    def test_allowlisted_commands_are_allowed(self) -> None:
        self.assertTrue(is_command_allowed("pwd"))
        self.assertTrue(is_command_allowed("git log --oneline -5"))
        self.assertFalse(is_command_allowed("git reset --hard"))

    def test_arbitrary_shell_command_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            decision = validator.validate(
                {"action": "run_command", "args": {"command": "whoami && dir"}, "risk": "medium"},
                user_command="run command whoami && dir",
            )
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.risk, "medium")

    def test_sensitive_requests_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            decision = validator.validate(
                {"action": "search_files", "args": {"query": "cookies"}, "risk": "low"},
                user_command="search files for cookies",
            )
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.risk, "high")

    def test_file_content_requests_are_blocked(self) -> None:
        self.assertTrue(contains_file_content_request("read file contents from notes.txt"))
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = SafetyValidator(make_config(Path(temp_dir)))
            decision = validator.validate(
                {"action": "search_files", "args": {"query": "notes"}, "risk": "low"},
                user_command="read file contents from notes.txt",
            )
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.risk, "high")


if __name__ == "__main__":
    unittest.main()
