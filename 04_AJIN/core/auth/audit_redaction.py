"""Secret-safe audit detail redaction helpers."""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|csrf|credential|secret|authorization|cookie|session)\b"
)
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|csrf|credential|secret|authorization|cookie|session)"
    r"\b\s*[:=]\s*([^\s,;]+)"
)
_JSON_VALUE_PATTERN = re.compile(
    r"(?i)([\"'](?:password|passwd|pwd|token|csrf|credential|secret|authorization|cookie|session)[\"']\s*:\s*)"
    r"([\"'][^\"']*[\"']|[^,}\s]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def redact_audit_detail(detail: Any) -> str:
    """Redact sensitive credential-like values from an audit detail string.

    Args:
        detail: Any audit detail value.

    Returns:
        str: Redacted detail safe for local SQLite, Postgres, and log sinks.
    """

    text = "" if detail is None else str(detail)
    if not text:
        return ""
    redacted = _JSON_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}\"[REDACTED]\"", text)
    redacted = _KEY_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)
    return redacted


def contains_sensitive_audit_marker(detail: Any) -> bool:
    """Return whether an audit detail still appears to contain sensitive markers.

    Args:
        detail: Audit detail value.

    Returns:
        bool: True when a sensitive key remains paired with a non-redacted value.
    """

    text = "" if detail is None else str(detail)
    for match in _KEY_VALUE_PATTERN.finditer(text):
        if "[REDACTED]" not in match.group(2):
            return True
    for match in _JSON_VALUE_PATTERN.finditer(text):
        if "[REDACTED]" not in match.group(2):
            return True
    bearer = _BEARER_PATTERN.search(text)
    return bool(bearer and "[REDACTED]" not in bearer.group(0))
