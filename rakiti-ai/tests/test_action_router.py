from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rakiti_ai.action_router import ActionRouter
from rakiti_ai.config import ButlerConfig, VoiceConfig
from rakiti_ai.logger import ActionLogger, redact_sensitive
from rakiti_ai.memory import LocalStore
from rakiti_ai.tools.open_app import open_app
from rakiti_ai.tools.open_url import open_url


def make_config(root: Path) -> ButlerConfig:
    return ButlerConfig(
        project_root=root,
        home_dir=root,
        os_name="windows",
        allowed_apps={
            "chrome": {"aliases": ["chrome", "google chrome"], "windows": "chrome"},
            "vscode": {"aliases": ["vscode", "vs code", "visual studio code"], "windows": "code"},
        },
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


class ActionRouterTests(unittest.TestCase):
    def test_create_folder_executes_after_safety_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            router = ActionRouter(make_config(root))
            result = router.execute({"action": "create_folder", "args": {"path": "Projects/TestApp"}, "risk": "low"})
            self.assertTrue(result.success)
            self.assertTrue((root / "Projects" / "TestApp").is_dir())

    def test_search_files_returns_names_and_paths_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "invoice-2026.txt").write_text("private content should not be read", encoding="utf-8")
            router = ActionRouter(make_config(root))
            result = router.execute({"action": "search_files", "args": {"query": "invoice"}, "risk": "low"})
            self.assertTrue(result.success)
            self.assertEqual(result.output[0]["name"], "invoice-2026.txt")
            self.assertIn("invoice-2026.txt", result.output[0]["path"])
            self.assertNotIn("private content", str(result.output))

    def test_show_system_info_executes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            router = ActionRouter(make_config(Path(temp_dir)))
            result = router.execute({"action": "show_system_info", "args": {}, "risk": "low"})
            self.assertTrue(result.success)
            self.assertIn("detected_os", result.output)

    def test_show_voice_devices_executes_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            router = ActionRouter(make_config(Path(temp_dir)))
            with patch("rakiti_ai.action_router.get_voice_device_report", return_value="Available local microphone inputs:"):
                result = router.execute({"action": "show_voice_devices", "args": {}, "risk": "low"})
            self.assertTrue(result.success)
            self.assertIn("microphone", result.output)

    def test_open_url_executes_with_safe_http_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            router = ActionRouter(make_config(Path(temp_dir)))
            with patch("rakiti_ai.tools.open_url.webbrowser.open", return_value=True):
                result = router.execute({"action": "open_url", "args": {"url": "https://example.com"}, "risk": "low"})
            self.assertTrue(result.success)
            self.assertEqual(result.output, "Opened URL: https://example.com")

    def test_open_url_rejects_suspicious_schemes(self) -> None:
        with self.assertRaises(ValueError):
            open_url("javascript:alert(1)")
        with self.assertRaises(ValueError):
            open_url("file:///C:/Windows/win.ini")

    def test_medium_action_requires_confirmation_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "old.txt").write_text("hello", encoding="utf-8")
            router = ActionRouter(make_config(root))
            result = router.execute(
                {
                    "action": "rename_file",
                    "args": {"source": "old.txt", "destination": "new.txt"},
                    "risk": "medium",
                }
            )
            self.assertFalse(result.success)
            self.assertEqual(result.status, "requires_confirmation")
            self.assertTrue((root / "old.txt").exists())

    def test_medium_action_executes_with_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "old.txt").write_text("hello", encoding="utf-8")
            router = ActionRouter(make_config(root))
            result = router.execute(
                {
                    "action": "rename_file",
                    "args": {"source": "old.txt", "destination": "new.txt"},
                    "risk": "medium",
                },
                confirmed=True,
            )
            self.assertTrue(result.success)
            self.assertTrue((root / "new.txt").exists())

    def test_logs_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalStore(root / "data" / "rakiti_ai.sqlite3")
            logger = ActionLogger(store)
            logger.log_action(
                user_command="show system info",
                parsed_action={"action": "show_system_info", "args": {}, "risk": "low"},
                risk_level="low",
                status="success",
            )
            self.assertEqual(store.count_actions(), 1)
            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["input_mode"], "text")

    def test_blocked_path_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            router = ActionRouter(make_config(root))
            result = router.execute({"action": "create_folder", "args": {"path": ".ssh/test"}, "risk": "low"})
            self.assertFalse(result.success)
            self.assertEqual(result.status, "failure")
            self.assertFalse((root / ".ssh" / "test").exists())

    def test_open_app_uses_allowlist_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_adapter = type("FakeAdapter", (), {"open_app_command": lambda self, command: None})()
            with patch("rakiti_ai.tools.open_app.get_adapter", return_value=fake_adapter):
                result = open_app("google chrome", make_config(root))
            self.assertEqual(result, "Opened app: chrome")

    def test_open_app_rejects_unknown_apps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "That app is not approved yet"):
                open_app("spotify", make_config(Path(temp_dir)))

    def test_windows_open_app_does_not_use_cmd_shell(self) -> None:
        from rakiti_ai.os_adapters.windows import open_app_command

        with patch("rakiti_ai.os_adapters.windows.subprocess.Popen") as popen:
            open_app_command("notepad")

        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ["notepad"])
        self.assertFalse(popen.call_args.kwargs["shell"])

    def test_log_redaction_covers_credential_terms(self) -> None:
        redacted = redact_sensitive("ssh key abc wallet seed keychain password token")
        self.assertIn("[REDACTED]", redacted)
        self.assertNotIn("abc", redacted)

    def test_create_and_list_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalStore(root / "data" / "rakiti_ai.sqlite3")
            router = ActionRouter(make_config(root), store=store)
            created = router.execute(
                {"action": "create_note", "args": {"title": "Shopping", "body": "buy tea"}, "risk": "low"}
            )
            listed = router.execute({"action": "list_notes", "args": {}, "risk": "low"})
            self.assertTrue(created.success)
            self.assertTrue(listed.success)
            self.assertEqual(listed.output[0]["title"], "Shopping")
            self.assertNotIn("buy tea", str(listed.output))

    def test_notes_do_not_store_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalStore(root / "data" / "rakiti_ai.sqlite3")
            router = ActionRouter(make_config(root), store=store)
            result = router.execute(
                {
                    "action": "create_note",
                    "args": {"title": "password", "body": "secret value"},
                    "risk": "low",
                }
            )
            self.assertFalse(result.success)
            self.assertIn("credentials or secrets", result.error_message)

    def test_preferences_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalStore(root / "data" / "rakiti_ai.sqlite3")
            router = ActionRouter(make_config(root), store=store)
            saved = router.execute(
                {"action": "set_preference", "args": {"key": "editor", "value": "vscode"}, "risk": "low"}
            )
            fetched = router.execute(
                {"action": "get_preference", "args": {"key": "editor"}, "risk": "low"}
            )
            self.assertTrue(saved.success)
            self.assertEqual(fetched.output, "editor: vscode")

    def test_help_executes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            router = ActionRouter(make_config(Path(temp_dir)))
            result = router.execute({"action": "help", "args": {}, "risk": "low"})
            self.assertTrue(result.success)
            self.assertIn("Supported commands", result.output)


if __name__ == "__main__":
    unittest.main()
