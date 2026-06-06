from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LocalLLMUnavailable(RuntimeError):
    pass


class LocalLLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    raw_output: str


class LocalLLMProvider(Protocol):
    def parse_intent(self, user_command: str) -> LLMResponse:
        pass
