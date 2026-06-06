from __future__ import annotations


HELP_TEXT = """Supported commands:
- open chrome / launch vscode / start calculator
- open https://example.com
- search files for invoice
- create folder Projects/TestApp
- create note Shopping: buy tea
- list notes
- set preference editor to vscode
- get preference editor
- show system info
- voice devices
- run command pwd

Safety:
- File search checks filenames only.
- Medium-risk actions require exact CONFIRM.
- Delete, credentials, cookies, tokens, screenshots, webcam, uploads, and arbitrary shell commands are blocked."""


def show_help() -> str:
    return HELP_TEXT
