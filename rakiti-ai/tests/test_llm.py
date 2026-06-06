from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from rakiti_ai.action_router import ActionRouter
from rakiti_ai.command_parser import CommandParser
from rakiti_ai.config import ButlerConfig, LLMConfig, VoiceConfig
from rakiti_ai.intent_parser import IntentParser
from rakiti_ai.llm.ollama_provider import ollama_chat_url
from rakiti_ai.llm.provider import LLMResponse, LocalLLMUnavailable
from rakiti_ai.llm.validator import LLMIntentValidationError, validate_llm_intent
from rakiti_ai.logger import ActionLogger
from rakiti_ai.main import handle_command, handle_voice_transcript
from rakiti_ai.memory import LocalStore
from rakiti_ai.safety import SafetyValidator
from rakiti_ai.voice import VoiceTranscript


def make_config(root: Path, *, llm_enabled: bool = True) -> ButlerConfig:
    return ButlerConfig(
        project_root=root,
        home_dir=root,
        os_name="windows",
        allowed_apps={
            "chrome": {"aliases": ["chrome", "google chrome"], "windows": "chrome"},
            "vscode": {"aliases": ["vscode", "vs code", "visual studio code"], "windows": "code"},
            "calculator": {"aliases": ["calculator", "calc"], "windows": "calc"},
            "file_explorer": {"aliases": ["file explorer", "explorer"], "windows": "explorer"},
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
        llm=LLMConfig(enabled=llm_enabled, timeout_seconds=1),
    )


class FakeProvider:
    def __init__(self, raw_output: str):
        self.raw_output = raw_output

    def parse_intent(self, user_command: str) -> LLMResponse:
        del user_command
        return LLMResponse(raw_output=self.raw_output)


class UnavailableProvider:
    def parse_intent(self, user_command: str) -> LLMResponse:
        del user_command
        raise LocalLLMUnavailable(
            "Local LLM is not available. Start Ollama manually or continue with the rule-based parser."
        )


class FailIfCalledProvider:
    def parse_intent(self, user_command: str) -> LLMResponse:
        raise AssertionError(f"LLM provider should not receive: {user_command}")


class CountingSafetyValidator(SafetyValidator):
    def __init__(self, config: ButlerConfig):
        super().__init__(config)
        self.calls = 0

    def validate(self, action: dict[str, object], *, user_command: str = ""):
        self.calls += 1
        return super().validate(action, user_command=user_command)


def raw_intent(
    action: str,
    args: dict[str, object],
    risk: str,
    confidence: float,
    reason: str = "test",
) -> str:
    return json.dumps(
        {
            "action": action,
            "args": args,
            "risk": risk,
            "confidence": confidence,
            "reason": reason,
        }
    )


class LLMValidatorTests(unittest.TestCase):
    def test_llm_output_valid_json_accepted(self) -> None:
        validated = validate_llm_intent(raw_intent("open_app", {"app_name": "chrome"}, "low", 0.95))
        self.assertEqual(validated.action["action"], "open_app")
        self.assertEqual(validated.action["args"], {"app_name": "chrome"})
        self.assertEqual(validated.confidence, 0.95)

    def test_llm_create_note_json_accepted(self) -> None:
        validated = validate_llm_intent(
            raw_intent("create_note", {"title": "Shopping", "body": "buy tea"}, "low", 0.95)
        )
        self.assertEqual(validated.action["action"], "create_note")

    def test_non_json_llm_output_rejected(self) -> None:
        with self.assertRaises(LLMIntentValidationError):
            validate_llm_intent("open chrome")

    def test_unknown_action_rejected(self) -> None:
        with self.assertRaises(LLMIntentValidationError):
            validate_llm_intent(raw_intent("delete_file", {"path": "Downloads"}, "high", 1.0))

    def test_missing_required_args_rejected(self) -> None:
        with self.assertRaises(LLMIntentValidationError):
            validate_llm_intent(raw_intent("open_app", {}, "low", 0.95))

    def test_empty_required_args_rejected(self) -> None:
        with self.assertRaises(LLMIntentValidationError):
            validate_llm_intent(raw_intent("open_url", {"url": "   "}, "low", 0.95))

    def test_low_confidence_rejected(self) -> None:
        with self.assertRaises(LLMIntentValidationError):
            validate_llm_intent(raw_intent("open_app", {"app_name": "chrome"}, "low", 0.3))

    def test_high_risk_action_blocked_by_validator(self) -> None:
        with self.assertRaises(LLMIntentValidationError):
            validate_llm_intent(raw_intent("blocked", {}, "high", 1.0, "File deletion is blocked."))

    def test_ollama_url_must_be_localhost_11434(self) -> None:
        self.assertEqual(ollama_chat_url("http://127.0.0.1:11434"), "http://127.0.0.1:11434/api/chat")
        self.assertEqual(ollama_chat_url("http://localhost:11434/"), "http://localhost:11434/api/chat")
        with self.assertRaises(LocalLLMUnavailable):
            ollama_chat_url("https://example.com")
        with self.assertRaises(LocalLLMUnavailable):
            ollama_chat_url("http://127.0.0.1:8080")


class LLMParserTests(unittest.TestCase):
    def test_open_chrome_maps_to_open_app_chrome(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = make_config(Path(temp_dir))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FakeProvider(raw_intent("open_app", {"app_name": "chrome"}, "low", 0.95)),
            )
            result = parser.parse("Can you open Chrome for me?")
            self.assertEqual(result.parser_used, "llm")
            self.assertEqual(result.action["action"], "open_app")
            self.assertEqual(result.action["args"], {"app_name": "chrome"})

    def test_rule_based_fallback_works_when_ollama_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = make_config(Path(temp_dir))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=UnavailableProvider(),
            )
            result = parser.parse("open chrome")
            self.assertEqual(result.parser_used, "rule_based")
            self.assertEqual(result.action["action"], "open_app")
            self.assertIn("Local LLM is not available", result.error_message or "")

    def test_sensitive_request_skips_llm_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = make_config(Path(temp_dir))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FailIfCalledProvider(),
            )
            result = parser.parse("read passwords")
            self.assertEqual(result.parser_used, "rule_based")
            self.assertEqual(result.action["action"], "blocked")
            self.assertIn("Skipped LLM parser", result.error_message or "")

    def test_file_content_request_skips_llm_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = make_config(Path(temp_dir))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FailIfCalledProvider(),
            )
            result = parser.parse("read file contents from notes.txt")
            self.assertEqual(result.parser_used, "rule_based")
            self.assertEqual(result.action["action"], "blocked")
            self.assertIn("Skipped LLM parser", result.error_message or "")

    def test_delete_downloads_is_blocked_after_llm_rejection_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = make_config(Path(temp_dir))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FakeProvider(raw_intent("blocked", {}, "high", 1.0, "File deletion is blocked.")),
            )
            result = parser.parse("delete downloads")
            self.assertEqual(result.parser_used, "rule_based")
            self.assertEqual(result.action["action"], "blocked")

    def test_read_passwords_is_blocked_after_llm_rejection_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = make_config(Path(temp_dir))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FakeProvider(raw_intent("blocked", {}, "high", 1.0, "Credential access is blocked.")),
            )
            result = parser.parse("read passwords")
            self.assertEqual(result.action["action"], "blocked")

    def test_run_rm_rf_is_blocked_by_safety_after_llm_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FakeProvider(raw_intent("run_command", {"command": "rm -rf /"}, "medium", 0.95)),
            )
            router = ActionRouter(config)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            handle_command("run rm -rf", parser=parser, router=router, logger=logger)
            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["status"], "blocked")
            self.assertEqual(latest["risk_level"], "high")

    def test_llm_output_still_goes_through_safety_py(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            safety = CountingSafetyValidator(config)
            router = ActionRouter(config, safety=safety)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FakeProvider(raw_intent("show_system_info", {}, "low", 0.95)),
            )
            handle_command("what computer is this", parser=parser, router=router, logger=logger)
            self.assertGreaterEqual(safety.calls, 1)
            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["parser_used"], "llm")

    def test_unknown_app_is_rejected_by_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            router = ActionRouter(config)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FakeProvider(raw_intent("open_app", {"app_name": "spotify"}, "low", 0.95)),
            )
            handle_command("open spotify", parser=parser, router=router, logger=logger)
            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["status"], "failure")
            self.assertIn("not approved", latest["error_message"])

    def test_voice_input_can_use_llm_parser_and_still_goes_through_safety(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            safety = CountingSafetyValidator(config)
            router = ActionRouter(config, safety=safety)
            logger = ActionLogger(LocalStore(root / "data" / "rakiti_ai.sqlite3"))
            parser = CommandParser(
                config,
                rule_parser=IntentParser(config.allowed_apps),
                llm_provider=FakeProvider(raw_intent("show_system_info", {}, "low", 0.95)),
            )
            handle_voice_transcript(
                VoiceTranscript("tell me about this computer", confidence=0.95),
                parser=parser,
                router=router,
                logger=logger,
                low_confidence_threshold=0.72,
            )
            self.assertGreaterEqual(safety.calls, 1)
            latest = logger.recent_actions(1)[0]
            self.assertEqual(latest["input_mode"], "voice")
            self.assertEqual(latest["parser_used"], "llm")

    def test_llm_mode_disabled_by_default_in_config_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            disabled_config = replace(make_config(Path(temp_dir)), llm=LLMConfig())
            self.assertFalse(disabled_config.llm.enabled)


if __name__ == "__main__":
    unittest.main()
