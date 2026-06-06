# Rafiki AI Agent Rules

This project is a local-first personal laptop-control assistant. Keep the code simple, readable, safe, and easy for a beginner to inspect. The Python module name is `rakiti_ai`; do not rename it unless there is a strong technical reason.

## Non-Negotiable Rules

- Keep the assistant local-first.
- Do not add cloud APIs.
- Do not add paid services.
- Do not add telemetry.
- Do not add secret handling.
- Do not add stealth behavior.
- Do not add hidden persistence.
- Do not add startup agents, launch daemons, scheduled tasks, cron jobs, services, or registry autostart entries.
- Do not access passwords, cookies, browser sessions, auth tokens, SSH keys, API keys, private keys, seed phrases, wallets, keychains, or credential stores.
- Do not read private file contents in version 1.

## Voice Rules

- Voice mode must never become always-on listening.
- Microphone use must always be explicit and user-initiated.
- Voice capture must be push-to-talk or one-shot only.
- Never save raw audio unless a future human-approved feature explicitly requires it.
- Never upload audio.
- Never add cloud speech-to-text.
- Never add wake-word background listening.
- Never let voice bypass `safety.py`.
- Voice transcripts must pass through the same parser, router, confirmation checks, allowlists, and logger as typed commands.

## LLM Rules

- LLM mode must be optional and disabled by default.
- LLM must never execute actions directly.
- LLM must only return structured intent JSON.
- LLM output must always be validated.
- LLM output must always pass through `safety.py`.
- Cloud LLM APIs are forbidden.
- API keys are forbidden.
- Do not add OpenAI, Claude, Gemini, Groq, Azure, AWS, Google Cloud, or hosted LLM providers.
- Ollama may be used only through local `127.0.0.1` or `localhost` configuration on port `11434`.
- Do not install Ollama automatically.
- Do not download models automatically.
- File contents must not be sent to the LLM.
- Credential-related requests must be blocked.
- Destructive actions must be blocked.
- Arbitrary shell execution must remain blocked.
- LLM raw output may be logged only after redaction; never log secrets or file contents.

## Safety Rules

- Any new tool must go through `safety.py`.
- New tools must be allowlisted and tested.
- Every new action must have tests.
- Any medium-risk action must require exact typed confirmation.
- Any high-risk action must be blocked.
- Do not allow arbitrary shell execution.
- Never add arbitrary shell execution.
- Never add file deletion in version 1.
- Keep `run_command` limited to the allowlist in `safety.py`.
- Never bypass OS permissions.
- Never disable antivirus, firewall, Gatekeeper, Defender, SIP, or security tools.
- Never pretend an action succeeded if it failed.

## Credential And Data Rules

- Never access credentials, cookies, sessions, tokens, keys, wallets, or keychains.
- Never inspect browser profile directories.
- Never inspect credential stores.
- Never upload files.
- Never send emails.
- Never use webcam, screenshots, keylogging, or background recording.

## Code Rules

- Use clear module boundaries.
- Keep functions small.
- Use type hints where practical.
- Prefer the Python standard library unless a feature requires a free local dependency.
- Avoid unnecessary dependencies.
- Preserve existing behavior unless explicitly asked to change it.
- Write tests for parser, safety, router, logging, voice handling, and any new tools.

## Completion Rule

No feature is complete unless:

- Tests pass.
- The README is updated.
- Behavior changes are documented in the README.
- The action is logged locally when run through the app.
- The action has passed through `safety.py`.
- Voice input is explicit and user-initiated.
- Medium/high-risk behavior is confirmed or blocked as required.
