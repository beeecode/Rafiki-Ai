from __future__ import annotations

import re


SENSITIVE_TEXT_PATTERNS = (
    r"\bpasswords?\b",
    r"\bpassphrases?\b",
    r"\bsecrets?\b",
    r"\btokens?\b",
    r"\bapi\s*keys?\b",
    r"\bprivate\s*keys?\b",
    r"\bssh\s*keys?\b",
    r"\bseed\s*phrases?\b",
    r"\bcookies?\b",
    r"\bwallets?\b",
    r"\bkeychains?\b",
    r"\bcredentials?\b",
)


def contains_sensitive_text(value: str) -> bool:
    normalized = value.casefold()
    return any(re.search(pattern, normalized) for pattern in SENSITIVE_TEXT_PATTERNS)


def reject_sensitive_text(value: str, *, context: str) -> None:
    if contains_sensitive_text(value):
        raise ValueError(
            f"{context} looks like it may contain credentials or secrets. "
            "Do not store passwords, tokens, keys, cookies, wallets, or seed phrases."
        )
