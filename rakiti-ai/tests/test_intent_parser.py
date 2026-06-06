from __future__ import annotations

import unittest

from rakiti_ai.intent_parser import IntentParser


class IntentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = IntentParser(
            {
                "chrome": {"aliases": ["chrome", "google chrome", "google", "browser"]},
                "vscode": {"aliases": ["vscode", "vs code", "visual studio code", "code editor"]},
                "calculator": {"aliases": ["calculator", "calc"]},
            }
        )

    def test_open_url_returns_structured_action(self) -> None:
        action = self.parser.parse("open https://example.com")
        self.assertEqual(action["action"], "open_url")
        self.assertEqual(action["args"], {"url": "https://example.com"})
        self.assertEqual(action["risk"], "low")

    def test_create_folder_returns_structured_action(self) -> None:
        action = self.parser.parse("create folder Projects/TestApp")
        self.assertEqual(action["action"], "create_folder")
        self.assertEqual(action["args"], {"path": "Projects/TestApp"})
        self.assertEqual(action["risk"], "low")

    def test_medium_risk_move_file(self) -> None:
        action = self.parser.parse("move file Downloads/test.pdf Documents/test.pdf")
        self.assertEqual(action["action"], "move_file")
        self.assertEqual(action["risk"], "medium")

    def test_high_risk_command_is_blocked(self) -> None:
        action = self.parser.parse("delete file old.txt")
        self.assertEqual(action["action"], "blocked")
        self.assertEqual(action["risk"], "high")

    def test_file_content_command_is_blocked(self) -> None:
        action = self.parser.parse("read file contents from notes.txt")
        self.assertEqual(action["action"], "blocked")
        self.assertEqual(action["risk"], "high")
        self.assertIn("File content inspection", action["args"]["reason"])

    def test_unclear_command_asks_for_clarification(self) -> None:
        action = self.parser.parse("please help with stuff")
        self.assertEqual(action["action"], "clarify")
        self.assertEqual(action["risk"], "none")

    def test_greeting_returns_helpful_guidance(self) -> None:
        action = self.parser.parse("hello")
        self.assertEqual(action["action"], "clarify")
        self.assertEqual(action["risk"], "none")
        self.assertIn("I am Rafiki AI", action["args"]["message"])

    def test_help_returns_supported_commands(self) -> None:
        action = self.parser.parse("help")
        self.assertEqual(action["action"], "help")
        self.assertEqual(action["risk"], "low")

    def test_polite_app_command_parses(self) -> None:
        action = self.parser.parse("Can you open Chrome for me?")
        self.assertEqual(action["action"], "open_app")
        self.assertEqual(action["args"], {"app_name": "chrome"})

    def test_natural_file_search_parses(self) -> None:
        action = self.parser.parse("Find invoice files")
        self.assertEqual(action["action"], "search_files")
        self.assertEqual(action["args"], {"query": "invoice"})

    def test_create_note_parses(self) -> None:
        action = self.parser.parse("create note Shopping: buy tea")
        self.assertEqual(action["action"], "create_note")
        self.assertEqual(action["args"], {"title": "Shopping", "body": "buy tea"})

    def test_list_notes_parses(self) -> None:
        action = self.parser.parse("list notes")
        self.assertEqual(action["action"], "list_notes")

    def test_preferences_parse(self) -> None:
        set_action = self.parser.parse("set preference editor to vscode")
        get_action = self.parser.parse("get preference editor")
        self.assertEqual(set_action["action"], "set_preference")
        self.assertEqual(set_action["args"], {"key": "editor", "value": "vscode"})
        self.assertEqual(get_action["action"], "get_preference")
        self.assertEqual(get_action["args"], {"key": "editor"})

    def test_voice_transcript_open_chrome_parses_to_canonical_app(self) -> None:
        action = self.parser.parse("open chrome")
        self.assertEqual(action["action"], "open_app")
        self.assertEqual(action["args"], {"app_name": "chrome"})
        self.assertEqual(action["risk"], "low")

    def test_voice_transcript_launch_vscode_parses_to_canonical_app(self) -> None:
        action = self.parser.parse("launch vscode")
        self.assertEqual(action["action"], "open_app")
        self.assertEqual(action["args"], {"app_name": "vscode"})
        self.assertEqual(action["risk"], "low")

    def test_voice_style_start_calculator_parses_to_open_app(self) -> None:
        action = self.parser.parse("start calculator")
        self.assertEqual(action["action"], "open_app")
        self.assertEqual(action["args"], {"app_name": "calculator"})

    def test_voice_devices_command_parses_to_diagnostic_action(self) -> None:
        action = self.parser.parse("voice devices")
        self.assertEqual(action["action"], "show_voice_devices")
        self.assertEqual(action["risk"], "low")

    def test_unknown_app_is_rejected_without_guessing(self) -> None:
        action = self.parser.parse("open spotify")
        self.assertEqual(action["action"], "clarify")
        self.assertIn("That app is not approved yet", action["args"]["message"])


if __name__ == "__main__":
    unittest.main()
