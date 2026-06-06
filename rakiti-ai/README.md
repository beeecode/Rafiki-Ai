# Rafiki AI

Rafiki AI is a local-first, zero-cost terminal assistant for basic laptop tasks. The Python module is still `rakiti_ai`, so the app runs with `python -m rakiti_ai`.

It uses a rule-based parser, optional local LLM intent parsing, an auditable safety layer, local SQLite logging, and OS-specific adapters for Windows, macOS, and Linux. Voice mode is push-to-talk only and uses local offline speech-to-text when the optional voice dependencies and a local Vosk model are installed.

Optional LLM mode is disabled by default. When enabled, it uses Ollama locally at `http://127.0.0.1:11434` or `http://localhost:11434` only. The LLM only converts a command into structured JSON. It never executes actions and never bypasses `safety.py`.

## What It Does

- Accepts typed commands.
- Accepts one-shot voice commands after explicit session consent.
- Optionally uses local Ollama to convert natural language into JSON intents.
- Opens allowlisted apps by typed or voice command.
- Opens `http://` and `https://` URLs.
- Searches filenames inside approved user directories.
- Creates folders inside approved user directories.
- Creates local SQLite notes after checking for secret-like content.
- Lists note titles and timestamps without dumping note bodies.
- Stores simple local preferences after checking for secret-like content.
- Handles simple safe multi-step requests step by step.
- Moves and renames files after exact typed confirmation.
- Shows basic system information.
- Runs a tiny allowlist of read-only commands after exact typed confirmation.
- Logs text, voice, and parser metadata locally to SQLite.

## What It Does Not Do

- It does not use cloud APIs.
- It does not use paid services.
- It does not use API keys.
- It does not use cloud LLM providers.
- It does not upload audio.
- It does not save raw audio by default.
- It does not listen in the background.
- It does not use wake words.
- It does not inspect file contents.
- It does not send file contents, credentials, cookies, sessions, tokens, keys, wallet data, keychain data, or credential-store data to an LLM.
- It does not access passwords, cookies, browser sessions, tokens, SSH keys, private keys, wallets, keychains, or credential stores.
- It does not install services, startup tasks, launch agents, cron jobs, scheduled tasks, or registry autostart entries.
- It does not run arbitrary shell commands.
- It does not delete files or folders in version 1.
- It does not upload files or send emails.
- It does not use the webcam, screenshots, or keylogging.

## Installation

From this folder:

```bash
python -m pip install -e .
```

No required runtime dependencies are needed beyond Python 3.11+.

## Run The App

From the project folder:

```bash
python -m rakiti_ai
```

You should see:

```text
Rafiki AI is running.
Input modes:
1. Type commands
2. Voice command
3. Help
4. Exit
LLM parser: disabled
Safety layer: enabled
```

Use an underscore for the Python module name. `python -m rakiti-ai` will not work because Python module names cannot contain hyphens.

## Typed Mode

Choose `1` to use typed commands.

```text
open chrome
open vscode
open https://example.com
search files for invoice
create folder Projects/TestApp
move file Downloads/test.pdf Documents/test.pdf
rename file old.txt new.txt
show system info
voice devices
create note Shopping: buy tea
list notes
set preference editor to vscode
get preference editor
run command pwd
```

Relative file paths are resolved inside your home directory. For example, `Documents/test.pdf` means `~/Documents/test.pdf`.

## Voice Mode

Choose `2` to use voice mode. On first voice use in a session, Rafiki AI prints a privacy notice and requires exact `ACCEPT`.

Rafiki AI asks you to press Enter before it records one short command. The microphone is not opened before that explicit action. Raw audio is not saved or uploaded.

If Rafiki AI says it could not understand you, switch to typed mode and run:

```text
voice devices
```

This lists local microphone inputs without recording audio. If the default microphone is wrong, set `voice.input_device` in `config.json`.

## Optional Local LLM Mode

LLM mode only improves parsing. It does not execute actions. The flow is:

```text
user command
-> local LLM intent parser
-> JSON schema validation
-> action router
-> safety.py
-> approved tool only
```

LLM mode is disabled by default:

```json
{
  "llm": {
    "enabled": false,
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "model": "llama3.2",
    "timeout_seconds": 10,
    "fallback_to_rule_parser": true
  }
}
```

To enable it, install and start Ollama manually, pull a model manually, then set `"enabled": true` in `config.json`.

Rafiki AI does not install Ollama, download models, use API keys, or call cloud LLM providers. If Ollama is unavailable, Rafiki AI falls back to the rule-based parser when configured. Requests involving credentials, secrets, cookies, sessions, tokens, keys, wallets, keychains, or file-content inspection skip the LLM parser and go straight to the conservative rule parser and safety layer.

## JSON Intent Schema

The local LLM must return only JSON:

```json
{
  "action": "open_app | open_url | search_files | create_folder | move_file | rename_file | show_system_info | run_command | create_note | list_notes | set_preference | get_preference | help | unclear | blocked",
  "args": {},
  "risk": "low | medium | high",
  "confidence": 0.0,
  "reason": "short explanation"
}
```

Rafiki AI rejects non-JSON output, unknown actions, missing required fields, missing required args, unknown args, confidence below `0.65`, high-risk LLM output, and mismatched risk levels. Accepted LLM output still passes through `safety.py`.

## Safety Model

Every typed, voice, or LLM-parsed command is converted into a structured action before it reaches a tool.

Low risk actions can run without confirmation:

- `open_app`
- `open_url`
- `search_files`
- `create_folder`
- `show_system_info`
- `create_note`
- `list_notes`
- `set_preference`
- `get_preference`
- `help`

Medium risk actions require exact typed confirmation:

- `move_file`
- `rename_file`
- `run_command`

High risk actions are blocked in version 1, including deletion, file-content inspection, credentials, cookies, sessions, tokens, keys, wallets, keychains, uploads, email, arbitrary shell commands, screenshots, webcam, keylogging, background recording, and hidden persistence.

## Multi-Step Commands

Rafiki AI can split simple safe requests into a plan:

```text
Create a folder called TestApp and open it in VS Code.
```

Each step is validated and logged separately:

```json
[
  {"action": "create_folder", "args": {"path": "Projects/TestApp"}, "risk": "low"},
  {"action": "open_app", "args": {"app_name": "vscode"}, "risk": "low"}
]
```

If any step is blocked, rejected, or fails, Rafiki stops the plan.

## Offline Speech-To-Text Setup

Voice mode uses optional free local packages:

- `sounddevice` captures explicit push-to-talk microphone input.
- `vosk` converts audio to text locally using a model on your laptop.

Install the optional voice dependencies:

```bash
python -m pip install -e ".[voice]"
```

Download a Vosk model manually and place it at:

```text
models/vosk-model-small-en-us-0.15
```

Or update `voice.model_path` in `config.json`.

## Approved App Allowlist

Apps are opened only when listed in `config.json`. If an app is not approved, Rafiki AI responds:

```text
That app is not approved yet. Add it to config first.
```

It does not guess, search your system, or run shell commands to find apps.

## Command Runner

`run_command` is not arbitrary shell access. It only allows:

- `pwd`
- `cd`
- `ls`
- `dir`
- `whoami`
- `python --version`
- `node --version`
- `git status`
- `git branch`
- `git log --oneline -5`

Dangerous strings such as `rm -rf`, `del /s`, `format`, `shutdown`, `reboot`, `reg delete`, `chmod 777 /`, `curl | sh`, `wget | sh`, `mkfs`, `diskpart`, `bcdedit`, and PowerShell encoded commands are rejected.

## Local Logs

Rafiki AI stores action logs in:

```text
data/rakiti_ai.sqlite3
```

The database includes timestamp, original command, input mode, transcript metadata, parser used, redacted LLM raw output, parser confidence, parsed action, risk level, status, and error message. Logs stay local. Raw audio is not logged or saved.

Local memory tables:

- `actions_log`
- `preferences`
- `notes`

Notes and preferences are local only. Do not store passwords, tokens, keys, cookies, wallets, or seed phrases in them.

## Configuration

Edit `config.json` to adjust app allowlists, approved directories, blocked directories, voice settings, and local LLM settings.

## Troubleshooting Local LLM

- If LLM mode says unavailable, start Ollama manually.
- If the model is missing, pull the model manually with Ollama.
- If LLM output is rejected, Rafiki AI falls back to the rule parser when configured.
- If `llm.base_url` is not local Ollama on port `11434`, Rafiki AI rejects it before making a request.
- If you do not need natural language parsing, leave `llm.enabled` as `false`.
- Never add cloud LLM URLs, API keys, or hosted model providers.

## Troubleshooting Voice

- If you see missing dependency errors, run `python -m pip install -e ".[voice]"`.
- If the model is missing, download a local Vosk model and update `voice.model_path`.
- If Rafiki hears nothing, choose typed mode and run `voice devices`, then set `voice.input_device`.
- If transcripts are poor, try a quieter room or a larger Vosk model.
- If voice mode is unavailable, typed mode remains available.

## Run Tests

```bash
python -m unittest discover -s tests
```

## Known Limitations

- The rule parser is intentionally conservative.
- Multi-step planning is intentionally simple and supports predictable commands only.
- LLM parsing depends on a manually managed local Ollama setup.
- Voice quality depends on the installed local Vosk model and microphone.
- File search checks filenames only, not file contents.
- File operations are restricted to configured user directories.
- File moves and renames never overwrite an existing destination in version 1.
- The command runner is a tiny read-only allowlist, not a shell.
