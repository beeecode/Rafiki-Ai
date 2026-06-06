from __future__ import annotations

import json
from urllib.error import URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from rakiti_ai.config import LLMConfig
from rakiti_ai.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from rakiti_ai.llm.provider import LLMResponse, LocalLLMError, LocalLLMUnavailable


ALLOWED_OLLAMA_HOSTS = {"127.0.0.1", "localhost"}
ALLOWED_OLLAMA_PORT = 11434


def ollama_chat_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in ALLOWED_OLLAMA_HOSTS or parsed.port != ALLOWED_OLLAMA_PORT:
        raise LocalLLMUnavailable(
            "Local LLM base_url must be http://127.0.0.1:11434 or http://localhost:11434."
        )
    return urlunparse((parsed.scheme, parsed.netloc, "/api/chat", "", "", ""))


class OllamaProvider:
    def __init__(self, config: LLMConfig):
        self.config = config

    def parse_intent(self, user_command: str) -> LLMResponse:
        payload = {
            "model": self.config.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(user_command)},
            ],
        }
        request = Request(
            ollama_chat_url(self.config.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except URLError as exc:
            raise LocalLLMUnavailable(
                "Local LLM is not available. Start Ollama manually or continue with the rule-based parser."
            ) from exc
        except TimeoutError as exc:
            raise LocalLLMUnavailable(
                "Local LLM timed out. Start Ollama manually or continue with the rule-based parser."
            ) from exc

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LocalLLMError("Ollama returned non-JSON response metadata.") from exc

        message = body.get("message")
        if not isinstance(message, dict):
            raise LocalLLMError("Ollama response did not include a message.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LocalLLMError("Ollama response did not include intent JSON.")
        return LLMResponse(raw_output=content.strip())
