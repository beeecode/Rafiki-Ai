from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rakiti_ai.llm.schemas import (
    ALLOWED_ARGS_BY_ACTION,
    ALLOWED_LLM_ACTIONS,
    ALLOWED_RISKS,
    LOW_RISK_ACTIONS,
    MEDIUM_RISK_ACTIONS,
    REQUIRED_ARGS_BY_ACTION,
    REQUIRED_FIELDS,
)


MIN_LLM_CONFIDENCE = 0.65


class LLMIntentValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedLLMIntent:
    action: dict[str, object]
    confidence: float
    reason: str


def validate_llm_intent(raw_output: str) -> ValidatedLLMIntent:
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise LLMIntentValidationError("LLM output was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise LLMIntentValidationError("LLM output must be a JSON object.")

    missing_fields = REQUIRED_FIELDS - set(data.keys())
    if missing_fields:
        raise LLMIntentValidationError(f"LLM output missing required fields: {', '.join(sorted(missing_fields))}")

    action_name = data.get("action")
    args = data.get("args")
    risk = data.get("risk")
    confidence = data.get("confidence")
    reason = data.get("reason")

    if not isinstance(action_name, str) or action_name not in ALLOWED_LLM_ACTIONS:
        raise LLMIntentValidationError("LLM output used an unknown action.")
    if not isinstance(args, dict):
        raise LLMIntentValidationError("LLM args must be an object.")
    if not isinstance(risk, str) or risk not in ALLOWED_RISKS:
        raise LLMIntentValidationError("LLM output used an unknown risk level.")
    if not isinstance(confidence, (int, float)):
        raise LLMIntentValidationError("LLM confidence must be numeric.")
    confidence_value = float(confidence)
    if confidence_value < MIN_LLM_CONFIDENCE:
        raise LLMIntentValidationError("LLM confidence was too low.")
    if not isinstance(reason, str) or not reason.strip():
        raise LLMIntentValidationError("LLM reason must be a short explanation.")

    allowed_args = ALLOWED_ARGS_BY_ACTION[action_name]
    unknown_args = set(str(key) for key in args.keys()) - allowed_args
    if unknown_args:
        raise LLMIntentValidationError(f"LLM output used unknown args: {', '.join(sorted(unknown_args))}")

    required_args = REQUIRED_ARGS_BY_ACTION[action_name]
    missing_args = required_args - set(str(key) for key in args.keys())
    if missing_args:
        raise LLMIntentValidationError(f"LLM output missing required args: {', '.join(sorted(missing_args))}")
    for required_arg in required_args:
        value = args.get(required_arg)
        if not _has_safe_required_value(value):
            raise LLMIntentValidationError(f"LLM output used an empty required arg: {required_arg}")

    if risk == "high" or action_name in {"blocked", "unclear"}:
        raise LLMIntentValidationError("LLM high-risk or unclear output is not executable.")

    expected_risk = _expected_risk(action_name)
    if risk != expected_risk:
        raise LLMIntentValidationError("LLM risk level did not match the allowed action risk.")

    return ValidatedLLMIntent(
        action={"action": action_name, "args": _stringify_args(args), "risk": risk},
        confidence=confidence_value,
        reason=reason.strip(),
    )


def _expected_risk(action_name: str) -> str:
    if action_name in LOW_RISK_ACTIONS:
        return "low"
    if action_name in MEDIUM_RISK_ACTIONS:
        return "medium"
    raise LLMIntentValidationError("LLM action is not executable.")


def _stringify_args(args: dict[Any, Any]) -> dict[str, object]:
    safe_args: dict[str, object] = {}
    for key, value in args.items():
        if value is None:
            continue
        safe_args[str(key)] = str(value) if not isinstance(value, (int, float, bool)) else value
    return safe_args


def _has_safe_required_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None
