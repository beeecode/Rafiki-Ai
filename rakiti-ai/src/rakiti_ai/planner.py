from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from rakiti_ai.command_parser import ParseResult


@dataclass(frozen=True)
class PlanStep:
    command_text: str
    parse_result: ParseResult


def build_plan(
    user_command: str,
    parse_func: Callable[[str], ParseResult],
) -> list[PlanStep] | None:
    if _should_skip_planning(user_command):
        return None

    parts = _split_multi_step_text(user_command)
    if len(parts) < 2:
        return None

    rewritten_parts = _rewrite_followup_steps(parts)
    steps = [PlanStep(command_text=part, parse_result=parse_func(part)) for part in rewritten_parts]
    meaningful_steps = [
        step for step in steps if str(step.parse_result.action.get("action")) != "clarify"
    ]
    if len(meaningful_steps) < 2:
        return None
    return steps


def _should_skip_planning(user_command: str) -> bool:
    lowered = user_command.strip().casefold()
    return lowered.startswith(("create note", "add note", "note "))


def _split_multi_step_text(user_command: str) -> list[str]:
    cleaned = user_command.strip().strip(".!?")
    parts = re.split(r"\s+(?:then|and then|and)\s+", cleaned, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _rewrite_followup_steps(parts: list[str]) -> list[str]:
    rewritten: list[str] = []
    for part in parts:
        lowered = part.casefold()
        if re.match(r"^open\s+it\s+in\s+", lowered):
            if "visual studio code" in lowered or "vs code" in lowered or "vscode" in lowered:
                rewritten.append("open vscode")
                continue
            if "file explorer" in lowered or "explorer" in lowered:
                rewritten.append("open file explorer")
                continue
        rewritten.append(part)
    return rewritten
