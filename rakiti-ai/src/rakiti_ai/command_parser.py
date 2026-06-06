from __future__ import annotations

from dataclasses import dataclass

from rakiti_ai.config import ButlerConfig
from rakiti_ai.intent_parser import IntentParser
from rakiti_ai.llm.ollama_provider import OllamaProvider
from rakiti_ai.llm.provider import LocalLLMError, LocalLLMProvider, LocalLLMUnavailable
from rakiti_ai.llm.validator import LLMIntentValidationError, validate_llm_intent
from rakiti_ai.safety import contains_file_content_request, contains_sensitive_request


def should_skip_llm_for_sensitive_request(user_command: str) -> bool:
    return contains_sensitive_request(user_command) or contains_file_content_request(user_command)


@dataclass(frozen=True)
class ParseResult:
    action: dict[str, object]
    parser_used: str
    llm_raw_output: str | None = None
    confidence: float | None = None
    error_message: str | None = None


class CommandParser:
    def __init__(
        self,
        config: ButlerConfig,
        *,
        rule_parser: IntentParser | None = None,
        llm_provider: LocalLLMProvider | None = None,
    ):
        self.config = config
        self.rule_parser = rule_parser or IntentParser(config.allowed_apps)
        self.llm_provider = llm_provider or self._build_provider()
        self.llm_available = True
        self.last_llm_unavailable_message: str | None = None

    def parse(self, user_command: str) -> ParseResult:
        if self.config.llm.enabled and should_skip_llm_for_sensitive_request(user_command):
            return self._rule_based(
                user_command,
                error_message="Skipped LLM parser for sensitive or file-content-related request.",
            )
        if self.config.llm.enabled and self.llm_provider is not None and self.llm_available:
            llm_result = self._try_llm_parse(user_command)
            if llm_result is not None:
                return llm_result
        return self._rule_based(user_command)

    def _try_llm_parse(self, user_command: str) -> ParseResult | None:
        try:
            response = self.llm_provider.parse_intent(user_command)
            validated = validate_llm_intent(response.raw_output)
            return ParseResult(
                action=validated.action,
                parser_used="llm",
                llm_raw_output=response.raw_output,
                confidence=validated.confidence,
            )
        except LocalLLMUnavailable as exc:
            self.llm_available = False
            self.last_llm_unavailable_message = str(exc)
            if not self.config.llm.fallback_to_rule_parser:
                return ParseResult(
                    action={"action": "clarify", "args": {"message": str(exc)}, "risk": "none"},
                    parser_used="llm",
                    error_message=str(exc),
                )
            return self._rule_based(user_command, error_message=str(exc))
        except (LocalLLMError, LLMIntentValidationError) as exc:
            if not self.config.llm.fallback_to_rule_parser:
                return ParseResult(
                    action={"action": "clarify", "args": {"message": "LLM parser failed. Please clarify."}, "risk": "none"},
                    parser_used="llm",
                    error_message=str(exc),
                )
            return self._rule_based(user_command, error_message=str(exc))

    def _rule_based(self, user_command: str, error_message: str | None = None) -> ParseResult:
        return ParseResult(
            action=self.rule_parser.parse(user_command),
            parser_used="rule_based",
            error_message=error_message,
        )

    def _build_provider(self) -> LocalLLMProvider | None:
        if not self.config.llm.enabled:
            return None
        if self.config.llm.provider != "ollama":
            return None
        return OllamaProvider(self.config.llm)
