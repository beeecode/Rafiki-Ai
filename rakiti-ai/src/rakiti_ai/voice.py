from __future__ import annotations

import json
import queue
import time
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from rakiti_ai.config import VoiceConfig


VOICE_PRIVACY_NOTICE = """Voice mode uses your microphone only after you press Enter.
Rafiki AI does not record in the background.
Audio is processed locally.
Audio is not saved.
Audio is not uploaded."""


class VoiceInputUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceTranscript:
    transcript: str
    confidence: float | None = None
    peak_level: float | None = None
    seconds_recorded: float | None = None
    heard_voice: bool = False


class VoiceRecognizer(Protocol):
    def listen_once(self) -> VoiceTranscript:
        pass


def ensure_voice_consent(
    *,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> bool:
    print_func(VOICE_PRIVACY_NOTICE)
    response = input_func("Type ACCEPT to enable voice mode for this session:\n").strip()
    return response == "ACCEPT"


def get_voice_device_report() -> str:
    sounddevice = _import_sounddevice()
    try:
        devices = sounddevice.query_devices()
        default_input = sounddevice.default.device[0]
    except Exception as exc:
        raise VoiceInputUnavailable(f"Could not query microphone devices: {exc}") from exc

    lines = ["Available local microphone inputs:"]
    for index, device in enumerate(devices):
        max_inputs = int(device.get("max_input_channels", 0))
        if max_inputs <= 0:
            continue
        marker = " (default)" if index == default_input else ""
        name = device.get("name", "Unknown device")
        lines.append(f"- {index}: {name}{marker}")

    if len(lines) == 1:
        lines.append("- No input devices reported by sounddevice.")
    lines.append('Set "voice.input_device" in config.json to one of these numbers if the default is wrong.')
    return "\n".join(lines)


def is_voice_available(config: VoiceConfig) -> bool:
    if not config.enabled:
        return False
    model_path = Path(config.model_path).expanduser().resolve(strict=False)
    if not model_path.exists():
        return False
    try:
        _import_sounddevice()
        import vosk  # noqa: F401
    except ImportError:
        return False
    return True


class VoiceInputSession:
    def __init__(self, recognizer_factory: Callable[[], VoiceRecognizer]):
        self.recognizer_factory = recognizer_factory

    def capture_once(
        self,
        *,
        input_func: Callable[[str], str] = input,
        print_func: Callable[[str], None] = print,
    ) -> VoiceTranscript:
        input_func("Press Enter and speak your command.\n")
        print_func("Listening...")
        recognizer = self.recognizer_factory()
        return recognizer.listen_once()


class OfflineVoskRecognizer:
    """Offline STT using local Vosk model files and sounddevice mic capture.

    This class intentionally saves no raw audio and sends no audio anywhere.
    """

    def __init__(self, config: VoiceConfig):
        self.config = config
        self.model_path = Path(config.model_path).expanduser().resolve(strict=False)

    def listen_once(self) -> VoiceTranscript:
        sounddevice, vosk = self._import_voice_dependencies()
        if not self.model_path.exists():
            raise VoiceInputUnavailable(
                "Offline voice model not found. Install a local Vosk model and set voice.model_path in config.json."
            )

        model = vosk.Model(str(self.model_path))
        recognizer = vosk.KaldiRecognizer(model, self.config.sample_rate)
        recognizer.SetWords(True)
        audio_queue: queue.Queue[bytes] = queue.Queue()
        started_speaking = False
        last_voice_at = time.monotonic()
        started_at = time.monotonic()
        peak_level = 0.0
        recognized_parts: list[str] = []
        confidence_values: list[float] = []
        last_partial = ""

        def callback(indata: bytes, frames: int, time_info: object, status: object) -> None:
            del frames, time_info, status
            audio_queue.put(bytes(indata))

        with sounddevice.RawInputStream(
            samplerate=self.config.sample_rate,
            blocksize=8000,
            dtype="int16",
            channels=1,
            device=self.config.input_device,
            callback=callback,
        ):
            while time.monotonic() - started_at < self.config.max_recording_seconds:
                try:
                    chunk = audio_queue.get(timeout=0.25)
                except queue.Empty:
                    continue

                accepted_phrase = recognizer.AcceptWaveform(chunk)
                if accepted_phrase:
                    phrase_result = json.loads(recognizer.Result())
                    _collect_vosk_result(phrase_result, recognized_parts, confidence_values)
                else:
                    partial_result = json.loads(recognizer.PartialResult())
                    last_partial = str(partial_result.get("partial", "")).strip()

                chunk_level = _chunk_level(chunk)
                peak_level = max(peak_level, chunk_level)
                if chunk_level >= self.config.silence_rms_threshold:
                    started_speaking = True
                    last_voice_at = time.monotonic()
                elif (
                    started_speaking
                    and time.monotonic() - last_voice_at >= self.config.silence_timeout_seconds
                ):
                    break

        final_result = json.loads(recognizer.FinalResult())
        _collect_vosk_result(final_result, recognized_parts, confidence_values)
        transcript = " ".join(part for part in recognized_parts if part).strip()
        if not transcript:
            transcript = last_partial
        confidence = _average(confidence_values)
        return VoiceTranscript(
            transcript=transcript,
            confidence=confidence,
            peak_level=peak_level,
            seconds_recorded=round(time.monotonic() - started_at, 2),
            heard_voice=started_speaking,
        )

    def _import_voice_dependencies(self) -> tuple[object, object]:
        try:
            import sounddevice
            import vosk
        except ImportError as exc:
            raise VoiceInputUnavailable(
                "Offline voice dependencies are not installed. Install with: python -m pip install -e .[voice]"
            ) from exc
        return sounddevice, vosk


def create_voice_session(config: VoiceConfig) -> VoiceInputSession:
    return VoiceInputSession(lambda: OfflineVoskRecognizer(config))


def _import_sounddevice() -> object:
    try:
        import sounddevice
    except ImportError as exc:
        raise VoiceInputUnavailable(
            "Offline voice dependencies are not installed. Install with: python -m pip install -e .[voice]"
        ) from exc
    return sounddevice


def _chunk_level(chunk: bytes) -> float:
    samples = array("h")
    samples.frombytes(chunk)
    if not samples:
        return 0.0
    return sum(abs(sample) for sample in samples) / len(samples)


def _confidence_from_vosk_result(result: dict[str, object]) -> float | None:
    words = result.get("result")
    if not isinstance(words, list) or not words:
        return None
    confidences = [
        float(word.get("conf", 0.0))
        for word in words
        if isinstance(word, dict) and isinstance(word.get("conf"), (int, float))
    ]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def _collect_vosk_result(
    result: dict[str, object],
    text_parts: list[str],
    confidences: list[float],
) -> None:
    text = str(result.get("text", "")).strip()
    if text:
        text_parts.append(text)
    words = result.get("result")
    if not isinstance(words, list):
        return
    for word in words:
        if isinstance(word, dict) and isinstance(word.get("conf"), (int, float)):
            confidences.append(float(word["conf"]))


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
