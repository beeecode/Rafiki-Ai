from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rakiti_ai.action_router import ActionRouter
from rakiti_ai.command_parser import CommandParser
from rakiti_ai.config import ButlerConfig, VoiceConfig
from rakiti_ai.intent_parser import IntentParser
from rakiti_ai.logger import ActionLogger
from rakiti_ai.main import handle_command
from rakiti_ai.memory import LocalStore
from rakiti_ai.planner import build_plan


def make_config(root: Path) -> ButlerConfig:
    return ButlerConfig(
        project_root=root,
        home_dir=root,
        os_name="windows",
        allowed_apps={
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


class PlannerTests(unittest.TestCase):
    def test_multi_step_command_builds_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = make_config(Path(temp_dir))
            parser = CommandParser(config, rule_parser=IntentParser(config.allowed_apps))
            plan = build_plan(
                "Create a folder called TestApp and open it in VS Code.",
                parser.parse,
            )
            self.assertIsNotNone(plan)
            self.assertEqual(plan[0].parse_result.action["action"], "create_folder")
            self.assertEqual(plan[0].parse_result.action["args"], {"path": "Projects/TestApp"})
            self.assertEqual(plan[1].parse_result.action["action"], "open_app")
            self.assertEqual(plan[1].parse_result.action["args"], {"app_name": "vscode"})

    def test_multi_step_execution_logs_each_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            store = LocalStore(root / "data" / "rakiti_ai.sqlite3")
            logger = ActionLogger(store)
            router = ActionRouter(config, store=store)
            parser = CommandParser(config, rule_parser=IntentParser(config.allowed_apps))
            fake_adapter = type("FakeAdapter", (), {"open_app_command": lambda self, command: None})()
            with patch("rakiti_ai.tools.open_app.get_adapter", return_value=fake_adapter):
                handle_command(
                    "Create a folder called TestApp and open it in VS Code.",
                    parser=parser,
                    router=router,
                    logger=logger,
                )
            self.assertTrue((root / "Projects" / "TestApp").is_dir())
            self.assertEqual(store.count_actions(), 2)

    def test_unsafe_plan_stops_before_later_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(root)
            store = LocalStore(root / "data" / "rakiti_ai.sqlite3")
            logger = ActionLogger(store)
            router = ActionRouter(config, store=store)
            parser = CommandParser(config, rule_parser=IntentParser(config.allowed_apps))
            handle_command(
                "delete downloads and open vscode",
                parser=parser,
                router=router,
                logger=logger,
            )
            self.assertEqual(store.count_actions(), 1)
            self.assertEqual(logger.recent_actions(1)[0]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
