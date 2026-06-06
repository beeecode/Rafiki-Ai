from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.2"
    timeout_seconds: float = 10.0
    fallback_to_rule_parser: bool = True


@dataclass(frozen=True)
class VoiceConfig:
    enabled: bool
    model_path: str
    input_device: int | str | None
    sample_rate: int
    max_duration_seconds: float
    silence_timeout_seconds: float
    silence_rms_threshold: int
    low_confidence_threshold: float
    max_recording_seconds: float = 6.0
    require_session_consent: bool = True


@dataclass(frozen=True)
class ButlerConfig:
    project_root: Path
    home_dir: Path
    os_name: str
    allowed_apps: dict[str, dict[str, Any]]
    allowed_directories: list[Path]
    blocked_directories: list[Path]
    max_search_results: int
    require_confirmation_for_medium_risk: bool
    data_dir: Path
    logs_dir: Path
    voice: VoiceConfig
    llm: LLMConfig = field(default_factory=LLMConfig)


def detect_os() -> str:
    system_name = platform.system().lower()
    if system_name == "windows":
        return "windows"
    if system_name == "darwin":
        return "macos"
    if system_name == "linux":
        return "linux"
    return system_name or "unknown"


def _expand_path(raw_path: str, home_dir: Path) -> Path:
    expanded = os.path.expandvars(raw_path)
    if expanded == "~" or expanded.startswith("~/") or expanded.startswith("~\\"):
        expanded = str(home_dir) + expanded[1:]
    return Path(expanded).expanduser().resolve(strict=False)


def load_config(config_path: Path | None = None) -> ButlerConfig:
    path = config_path or DEFAULT_CONFIG_PATH
    with path.open("r", encoding="utf-8") as config_file:
        raw: dict[str, Any] = json.load(config_file)

    home_dir = Path.home().resolve(strict=False)
    project_root = path.resolve(strict=False).parent
    allowed_dirs = [
        _expand_path(str(item), home_dir)
        for item in raw.get("allowed_directories", [])
    ]
    blocked_dirs = [
        _expand_path(str(item), home_dir)
        for item in raw.get("blocked_directories", [])
    ]

    data_dir = project_root / "data"
    logs_dir = project_root / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    raw_voice = raw.get("voice", {})
    if not isinstance(raw_voice, dict):
        raw_voice = {}
    raw_llm = raw.get("llm", {})
    if not isinstance(raw_llm, dict):
        raw_llm = {}

    return ButlerConfig(
        project_root=project_root,
        home_dir=home_dir,
        os_name=detect_os(),
        allowed_apps=raw.get("allowed_apps", {}),
        allowed_directories=allowed_dirs,
        blocked_directories=blocked_dirs,
        max_search_results=int(raw.get("max_search_results", 25)),
        require_confirmation_for_medium_risk=bool(
            raw.get("require_confirmation_for_medium_risk", True)
        ),
        data_dir=data_dir,
        logs_dir=logs_dir,
        voice=VoiceConfig(
            enabled=bool(raw_voice.get("enabled", True)),
            model_path=str(raw_voice.get("model_path", "models/vosk-model-small-en-us-0.15")),
            input_device=raw_voice.get("input_device"),
            sample_rate=int(raw_voice.get("sample_rate", 16000)),
            max_duration_seconds=float(
                raw_voice.get("max_duration_seconds", raw_voice.get("max_recording_seconds", 6.0))
            ),
            max_recording_seconds=float(
                raw_voice.get("max_recording_seconds", raw_voice.get("max_duration_seconds", 6.0))
            ),
            silence_timeout_seconds=float(raw_voice.get("silence_timeout_seconds", 1.2)),
            silence_rms_threshold=int(raw_voice.get("silence_rms_threshold", 500)),
            low_confidence_threshold=float(raw_voice.get("low_confidence_threshold", 0.72)),
            require_session_consent=bool(raw_voice.get("require_session_consent", True)),
        ),
        llm=LLMConfig(
            enabled=bool(raw_llm.get("enabled", False)),
            provider=str(raw_llm.get("provider", "ollama")),
            base_url=str(raw_llm.get("base_url", "http://127.0.0.1:11434")),
            model=str(raw_llm.get("model", "llama3.2")),
            timeout_seconds=float(raw_llm.get("timeout_seconds", 10)),
            fallback_to_rule_parser=bool(raw_llm.get("fallback_to_rule_parser", True)),
        ),
    )
