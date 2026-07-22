"""Telemetry sanitizer (section 20): credentials, board IPs, and personal
paths never reach persisted records or corpus tuples."""

import re
from typing import Any

_PATTERNS = (
    # API keys and bearer-style tokens.
    (re.compile(r"sk-[A-Za-z0-9_-]{10,}"), "[REDACTED-KEY]"),
    (re.compile(r"(?i)\b(bearer|token|apikey|api_key|password)\s*[=:]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "[REDACTED-KEY]"),
    # IPv4 addresses (board hosts).
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[REDACTED-IP]"),
    # Personal home paths.
    (re.compile(r"/home/[A-Za-z0-9._-]+"), "/home/[USER]"),
    (re.compile(r"/Users/[A-Za-z0-9._-]+"), "/Users/[USER]"),
    # SSH private key blocks.
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "[REDACTED-PRIVATE-KEY]",
    ),
)


def sanitize_text(text: str) -> str:
    """Redact secrets, IPs, and personal paths from free text."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """Sanitize string keys and values of a flat mapping."""
    clean: dict[str, Any] = {}
    for key, value in mapping.items():
        clean_key = sanitize_text(str(key))
        clean[clean_key] = sanitize_text(value) if isinstance(value, str) else value
    return clean
