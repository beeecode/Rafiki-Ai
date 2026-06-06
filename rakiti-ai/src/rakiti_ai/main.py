from __future__ import annotations

import json
from typing import Any

from rakiti_ai.action_router import ActionResult, ActionRouter
from rakiti_ai.command_parser import CommandParser, ParseResult
from rakiti_ai.config import ButlerConfig, load_config
from rakiti_ai.intent_parser import IntentParser
from rakiti_ai.logger import ActionLogger
from rakiti_ai.memory import LocalStore
from rakiti_ai.permissions import get_action_args, summarize_action
from rakiti_ai.planner import build_plan
from rakiti_ai.voice import VoiceInputUnavailable, VoiceTranscript, create_voice_session, ensure_voice_consent
from rakiti_ai.voice import is_voice_available


def _format_output(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, list):
        if not output:
            return "No results found."
        if all(isinstance(item, dict) and "title" in item for item in output):
            return "\n".join(
                f"{item.get('id')}: {item.get('title')} - updated {item.get('updated_at')}"
                for item in output
            )
        return "\n".join(f"{item.get('name')} - {item.get('path')}" for item in output)
    if isinstance(output, dict):
        return json.dumps(output, indent=2, sort_keys=True)
    return str(output)


def _log_result(
    logger: ActionLogger,
    *,
    user_command: str,
    parsed_action: dict[str, object],
    risk_level: str,
    result: ActionResult,
    input_mode: str,
    transcript: str | None,
    transcript_confidence: float | None,
    parser_used: str,
    llm_raw_output: str | None,
    confidence: float | None,
) -> None:
    logger.log_action(
        user_command=user_command,
        parsed_action=parsed_action,
        risk_level=risk_level,
        status=result.status,
        error_message=result.error_message,
        input_mode=input_mode,
        transcript=transcript,
        transcript_confidence=transcript_confidence,
        parser_used=parser_used,
        llm_raw_output=llm_raw_output,
        confidence=confidence,
    )


def handle_command(
    user_command: str,
    *,
    parser: Any,
    router: ActionRouter,
    logger: ActionLogger,
    input_mode: str = "text",
    transcript: str | None = None,
    transcript_confidence: float | None = None,
    show_parsed: bool = False,
) -> None:
    plan_steps = build_plan(user_command, lambda step: _parse_with_metadata(parser, step))
    if plan_steps:
        print(f"Plan: {len(plan_steps)} steps")
        for index, step in enumerate(plan_steps, start=1):
            print(f"Step {index}/{len(plan_steps)}: {step.command_text}")
            should_continue = _handle_parse_result(
                step.parse_result,
                user_command=step.command_text,
                router=router,
                logger=logger,
                input_mode=input_mode,
                transcript=transcript,
                transcript_confidence=transcript_confidence,
                show_parsed=True,
            )
            if not should_continue:
                print("Plan stopped.")
                return
        return

    parse_result = _parse_with_metadata(parser, user_command)
    _handle_parse_result(
        parse_result,
        user_command=user_command,
        router=router,
        logger=logger,
        input_mode=input_mode,
        transcript=transcript,
        transcript_confidence=transcript_confidence,
        show_parsed=show_parsed,
    )


def _handle_parse_result(
    parse_result: ParseResult,
    *,
    user_command: str,
    router: ActionRouter,
    logger: ActionLogger,
    input_mode: str,
    transcript: str | None,
    transcript_confidence: float | None,
    show_parsed: bool,
) -> bool:
    if parse_result.error_message and "Local LLM" in parse_result.error_message:
        print(parse_result.error_message)
    action = parse_result.action
    action_name = str(action.get("action", ""))
    args = get_action_args(action)

    if show_parsed:
        print(f"Parsed action: {action_name}")
        print(f"Parser: {parse_result.parser_used}")

    if action_name == "clarify":
        message = str(args.get("message", "Clarification needed."))
        print(message)
        logger.log_action(
            user_command=user_command,
            parsed_action=action,
            risk_level="none",
            status="clarification_needed",
            error_message=message,
            input_mode=input_mode,
            transcript=transcript,
            transcript_confidence=transcript_confidence,
            parser_used=parse_result.parser_used,
            llm_raw_output=parse_result.llm_raw_output,
            confidence=parse_result.confidence,
        )
        return False

    decision = router.check_safety(action, user_command=user_command)
    if show_parsed:
        print(f"Risk: {decision.risk}")
    if not decision.allowed:
        print(f"Blocked: {decision.reason}")
        suggestion = _safe_alternative(decision.reason)
        if suggestion:
            print(f"Safe alternative: {suggestion}")
        logger.log_action(
            user_command=user_command,
            parsed_action=action,
            risk_level=decision.risk,
            status="blocked",
            error_message=decision.reason,
            input_mode=input_mode,
            transcript=transcript,
            transcript_confidence=transcript_confidence,
            parser_used=parse_result.parser_used,
            llm_raw_output=parse_result.llm_raw_output,
            confidence=parse_result.confidence,
        )
        return False

    confirmed = False
    if decision.requires_confirmation:
        print("This action requires confirmation:")
        print(summarize_action(action))
        confirmation = input("Type CONFIRM to continue:\n").strip()
        if confirmation != "CONFIRM":
            print("Cancelled.")
            logger.log_action(
                user_command=user_command,
                parsed_action=action,
                risk_level=decision.risk,
                status="rejected",
                error_message="User did not provide exact confirmation.",
                input_mode=input_mode,
                transcript=transcript,
                transcript_confidence=transcript_confidence,
                parser_used=parse_result.parser_used,
                llm_raw_output=parse_result.llm_raw_output,
                confidence=parse_result.confidence,
            )
            return False
        confirmed = True

    if show_parsed:
        print("Executing...")
    result = router.execute(action, user_command=user_command, confirmed=confirmed)
    _log_result(
        logger,
        user_command=user_command,
        parsed_action=action,
        risk_level=result.risk_level or decision.risk,
        result=result,
        input_mode=input_mode,
        transcript=transcript,
        transcript_confidence=transcript_confidence,
        parser_used=parse_result.parser_used,
        llm_raw_output=parse_result.llm_raw_output,
        confidence=parse_result.confidence,
    )

    if result.success:
        formatted = _format_output(result.output)
        if formatted:
            print(formatted)
        return True
    else:
        print(f"Failed: {result.error_message}")
        return False


def _parse_with_metadata(parser: Any, user_command: str) -> ParseResult:
    parsed = parser.parse(user_command)
    if isinstance(parsed, ParseResult):
        return parsed
    if isinstance(parsed, dict):
        return ParseResult(action=parsed, parser_used="rule_based")
    return ParseResult(
        action={"action": "clarify", "args": {"message": "Parser returned an invalid result."}, "risk": "none"},
        parser_used="rule_based",
        error_message="Parser returned an invalid result.",
    )


def _safe_alternative(reason: str) -> str:
    lowered = reason.casefold()
    if "deleting" in lowered or "delete" in lowered:
        return "Use search_files to find files, then move or rename only approved files with confirmation."
    if "credential" in lowered or "secret" in lowered or "password" in lowered:
        return "Ask for help with non-sensitive local tasks, or store non-secret preferences only."
    if "command" in lowered:
        return "Use one of the restricted commands: pwd, dir, ls, whoami, python --version, node --version, git status, git branch, git log --oneline -5."
    if "unknown" in lowered or "unapproved" in lowered:
        return "Add a safe tool or app alias to config first, then try again."
    return ""


def handle_voice_transcript(
    voice_result: VoiceTranscript,
    *,
    parser: IntentParser,
    router: ActionRouter,
    logger: ActionLogger,
    low_confidence_threshold: float,
) -> None:
    transcript = voice_result.transcript.strip()
    if not transcript:
        if voice_result.heard_voice:
            message = (
                "I heard audio, but could not turn it into a command. "
                "Try speaking a little slower, closer to the microphone, or use typed mode."
            )
        else:
            message = (
                "I did not hear speech from the selected microphone. "
                "Check Windows microphone permission, then use typed mode command: voice devices."
            )
        print(message)
        if voice_result.peak_level is not None:
            print(f"Peak input level: {voice_result.peak_level:.0f}")
        logger.log_action(
            user_command="",
            parsed_action={"action": "clarify", "args": {"message": message}, "risk": "none"},
            risk_level="none",
            status="transcription_unclear",
            error_message=message,
            input_mode="voice",
            transcript="",
            transcript_confidence=voice_result.confidence,
            parser_used="rule_based",
        )
        return

    print(f"You said: {transcript}")
    if (
        voice_result.confidence is not None
        and voice_result.confidence < low_confidence_threshold
    ):
        print(f"Transcript confidence is low: {voice_result.confidence:.2f}")
        confirmation = input("Type CONFIRM to execute this transcript:\n").strip()
        if confirmation != "CONFIRM":
            print("Cancelled.")
            logger.log_action(
                user_command=transcript,
                parsed_action={"action": "clarify", "args": {"message": "Low-confidence transcript rejected."}, "risk": "none"},
                risk_level="none",
                status="rejected",
                error_message="Low-confidence voice transcript was not confirmed.",
                input_mode="voice",
                transcript=transcript,
                transcript_confidence=voice_result.confidence,
                parser_used="rule_based",
            )
            return

    handle_command(
        transcript,
        parser=parser,
        router=router,
        logger=logger,
        input_mode="voice",
        transcript=transcript,
        transcript_confidence=voice_result.confidence,
        show_parsed=True,
    )


def run_text_mode(parser: IntentParser, router: ActionRouter, logger: ActionLogger) -> int:
    print('Type a command, or type "exit".')

    while True:
        try:
            user_command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if user_command.lower() in {"exit", "quit"}:
            return 0
        if not user_command:
            continue

        handle_command(user_command, parser=parser, router=router, logger=logger)


def run_voice_mode(
    *,
    config: ButlerConfig,
    parser: IntentParser,
    router: ActionRouter,
    logger: ActionLogger,
    voice_consent_granted: bool,
) -> bool:
    if not config.voice.enabled:
        message = "Voice mode is disabled in config.json. Falling back to typed mode."
        print(message)
        logger.log_action(
            user_command="",
            parsed_action={"action": "clarify", "args": {"message": message}, "risk": "none"},
            risk_level="none",
            status="voice_unavailable",
            error_message=message,
            input_mode="voice",
        )
        run_text_mode(parser, router, logger)
        return voice_consent_granted

    if config.voice.require_session_consent and not voice_consent_granted:
        voice_consent_granted = ensure_voice_consent()
        if not voice_consent_granted:
            message = "Voice mode disabled for this session."
            print(message)
            logger.log_action(
                user_command="",
                parsed_action={"action": "clarify", "args": {"message": message}, "risk": "none"},
                risk_level="none",
                status="voice_consent_rejected",
                error_message=message,
                input_mode="voice",
            )
            return False

    session = create_voice_session(config.voice)
    try:
        voice_result = session.capture_once()
    except VoiceInputUnavailable as exc:
        print(str(exc))
        print("Falling back to typed mode.")
        logger.log_action(
            user_command="",
            parsed_action={"action": "clarify", "args": {"message": str(exc)}, "risk": "none"},
            risk_level="none",
            status="voice_unavailable",
            error_message=str(exc),
            input_mode="voice",
        )
        run_text_mode(parser, router, logger)
        return voice_consent_granted

    handle_voice_transcript(
        voice_result,
        parser=parser,
        router=router,
        logger=logger,
        low_confidence_threshold=config.voice.low_confidence_threshold,
    )
    return voice_consent_granted


def run_repl() -> int:
    config = load_config()
    store = LocalStore(config.data_dir / "rakiti_ai.sqlite3")
    logger = ActionLogger(store)
    parser = CommandParser(config, rule_parser=IntentParser(config.allowed_apps))
    router = ActionRouter(config, store=store)
    voice_consent_granted = False

    print("Rafiki AI is running.")
    print("Safety layer: enabled")
    print(f"LLM parser: {'enabled' if config.llm.enabled else 'disabled'}")
    print(f"Voice mode: {'available' if is_voice_available(config.voice) else 'unavailable'}")

    while True:
        try:
            print("Choose input mode:")
            print("1. Type commands")
            print("2. Voice command")
            print("3. Help")
            print("4. Exit")
            choice = input("Choose input mode: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice in {"1", "type", "text"}:
            return run_text_mode(parser, router, logger)
        if choice in {"2", "voice"}:
            voice_consent_granted = run_voice_mode(
                config=config,
                parser=parser,
                router=router,
                logger=logger,
                voice_consent_granted=voice_consent_granted,
            )
            continue
        if choice in {"3", "help", "?"}:
            handle_command("help", parser=parser, router=router, logger=logger)
            continue
        if choice in {"4", "exit", "quit"}:
            return 0
        print("Choose 1, 2, 3, or 4.")


def main() -> int:
    return run_repl()


if __name__ == "__main__":
    raise SystemExit(main())
