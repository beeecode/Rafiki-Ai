from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rakiti_ai.action_router import ActionRouter
from rakiti_ai.config import ButlerConfig, VoiceConfig
from rakiti_ai.intent_parser import IntentParser
from rakiti_ai.logger import ActionLogger
from rakiti_ai.main import handle_command, handle_voice_transcript
from rakiti_ai.memory import LocalStore
from rakiti_ai.safety import SafetyValidator
from rakiti_ai.voice import VoiceInputSession, VoiceTranscript, ensure_voice_consent


def make_config(root: Path) -> ButlerConfig:
    return ButlerConfig(
        project_root=root,
        home_dir=root,
        os_name="windows",
        allowed_apps={
            "chrome": {"aliases": ["chrome", "google chrome", "google"], "windows": "chrome"},
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


class CountingSafetyValidator(SafetyValidator):
    def __init__(self, config: ButlerConfig):
        super().__init__(config)
        self.calls = 0

    def validate(self, action: dict[str, object], *, user_command: str = ""):
        self.calls += 1
        return super().validate(action, user_command=user_command)


class VoiceTests(unittest.TestCase):
    def test_voice_commands_go_through_safety(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            safety = CountingSafetyValidator(config)
            router = ActionRouter(config, safety=safety)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = IntentParser(config.allowed_apps)

            handle_voice_transcript(
                VoiceTranscript("show system info", confidence=0.95),
                parser=parser,
                router=router,
                logger=logger,
                low_confidence_threshold=0.72,
            )

            self.assertGreaterEqual(safety.calls, 1)
            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["input_mode"], "voice")
            self.assertEqual(latest["transcript"], "show system info")

    def test_blocked_actions_remain_blocked_from_voice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            router = ActionRouter(config)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = IntentParser(config.allowed_apps)

            handle_voice_transcript(
                VoiceTranscript("delete file old.txt", confidence=0.95),
                parser=parser,
                router=router,
                logger=logger,
                low_confidence_threshold=0.72,
            )

            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["status"], "blocked")
            self.assertEqual(latest["risk_level"], "high")

    def test_dangerous_commands_are_not_executed_from_voice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            router = ActionRouter(config)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = IntentParser(config.allowed_apps)

            handle_voice_transcript(
                VoiceTranscript("run command rm -rf /", confidence=0.95),
                parser=parser,
                router=router,
                logger=logger,
                low_confidence_threshold=0.72,
            )

            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["status"], "blocked")
            self.assertEqual(latest["risk_level"], "high")

    def test_microphone_capture_does_not_start_automatically(self) -> None:
        started = {"value": False}

        class FakeRecognizer:
            def listen_once(self) -> VoiceTranscript:
                return VoiceTranscript("open chrome", confidence=0.95, heard_voice=True)

        def factory() -> FakeRecognizer:
            started["value"] = True
            return FakeRecognizer()

        session = VoiceInputSession(factory)
        self.assertFalse(started["value"])
        transcript = session.capture_once(input_func=lambda prompt: "", print_func=lambda text: None)
        self.assertTrue(started["value"])
        self.assertEqual(transcript.transcript, "open chrome")

    def test_voice_consent_requires_exact_accept(self) -> None:
        self.assertFalse(ensure_voice_consent(input_func=lambda prompt: "accept", print_func=lambda text: None))
        self.assertTrue(ensure_voice_consent(input_func=lambda prompt: "ACCEPT", print_func=lambda text: None))

    def test_unclear_voice_logs_no_speech_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            router = ActionRouter(config)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = IntentParser(config.allowed_apps)

            handle_voice_transcript(
                VoiceTranscript("", confidence=None, peak_level=12.0, heard_voice=False),
                parser=parser,
                router=router,
                logger=logger,
                low_confidence_threshold=0.72,
            )

            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["status"], "transcription_unclear")
            self.assertIn("did not hear speech", latest["error_message"])

    def test_text_mode_still_uses_same_command_handler(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            router = ActionRouter(config)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = IntentParser(config.allowed_apps)

            handle_command("show system info", parser=parser, router=router, logger=logger)

            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["input_mode"], "text")
            self.assertEqual(latest["status"], "success")

    def test_voice_open_chrome_can_execute_when_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            router = ActionRouter(config)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = IntentParser(config.allowed_apps)
            fake_adapter = type("FakeAdapter", (), {"open_app_command": lambda self, command: None})()

            with patch("rakiti_ai.tools.open_app.get_adapter", return_value=fake_adapter):
                handle_voice_transcript(
                    VoiceTranscript("open chrome", confidence=0.95),
                    parser=parser,
                    router=router,
                    logger=logger,
                    low_confidence_threshold=0.72,
                )

            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["status"], "success")
            self.assertIn('"app_name": "chrome"', latest["parsed_action"])


if __name__ == "__main__":
    unittest.main()
