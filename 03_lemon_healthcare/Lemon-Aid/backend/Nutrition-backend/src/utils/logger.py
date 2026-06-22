"""애플리케이션 로깅 설정 + PII redaction.

Logs that flow through the standard :mod:`logging` module are passed through
a :class:`RedactingFilter` that masks common secret/PII payloads (DB-URL
credentials, Authorization headers, bearer tokens, bare JWTs, API keys, Korean
phone numbers, emails, long hex blobs) before formatting. Redaction is applied
to the rendered message, to string values in ``extra={...}`` dicts, and to
attached exception tracebacks, so secrets cannot leak through any of those
channels regardless of how caller code interpolates arguments.
"""

from __future__ import annotations

import logging
import re
import sys

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Database URL credentials (e.g. postgresql+asyncpg://{user}:{password}@{host})
    # — mask the password only, keep scheme/host so connection errors stay diagnosable.
    (
        re.compile(r"(?P<scheme>[a-z][a-z0-9+.\-]*://)(?P<user>[^:/@\s]+):[^@/\s]+@"),
        r"\g<scheme>\g<user>:***@",
    ),
    # Authorization header value, regardless of scheme (Bearer/Basic/...).
    (re.compile(r"(?i)(authorization)\s*[:=]\s*\S+"), r"\1: ***REDACTED***"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]+", re.IGNORECASE), "Bearer ***REDACTED***"),
    # Bare JWTs (Supabase anon/service-role keys, access tokens) without a Bearer prefix.
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "***JWT***"),
    # Common API-key prefixes (Stripe, Supabase, Google).
    (re.compile(r"\b(?:sk-|sk_live_|sk_test_|sbp_|AIza)[A-Za-z0-9_\-]{16,}\b"), "***APIKEY***"),
    # Korean mobile numbers (01X-XXXX-XXXX), optional hyphens — PII for a health app.
    (re.compile(r"\b01[0-9]-?\d{3,4}-?\d{4}\b"), "***PHONE***"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "***EMAIL***"),
    # Long hex blobs (>=40) that are NOT short internal request/audit ids. 40 hex
    # chars covers SHA-1/256 token-like material while leaving 32-char request ids
    # and shorter correlation hashes legible for incident response.
    (re.compile(r"\b[a-f0-9]{40,}\b"), "***HASH***"),
)
"""Ordered ``(pattern, replacement)`` pairs applied to every log message."""


def _redact_text(text: str) -> str:
    """Apply every redaction pattern to a single string.

    Args:
        text: Raw string that may contain secrets/PII.

    Returns:
        The string with all known secret/PII shapes masked.
    """
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# Built-in LogRecord attributes that must not be treated as user-supplied extras
# (and a couple we already handle explicitly: msg/args/exc_text).
_STANDARD_LOGRECORD_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }
)


class RedactingFilter(logging.Filter):
    """Mask common PII patterns in log records before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask PII/secret shapes across message, args-extras, and tracebacks.

        Redaction is applied to (1) the rendered message string, (2) string
        values in ``record.__dict__`` extras (``logger.info(..., extra={...})``),
        and (3) any attached exception traceback, which the handler's formatter
        would otherwise emit verbatim after this filter runs.

        Args:
            record: Log record about to be emitted.

        Returns:
            ``True`` so the record continues through the logging pipeline.
        """
        # Redact the message template and any args IN PLACE, preserving the args
        # container shape. We must NOT pre-render and null ``record.args``: some
        # formatters (notably uvicorn's AccessFormatter) unpack the args tuple
        # themselves — ``(addr, method, path, ver, status) = record.args`` — so
        # clearing it raises "cannot unpack non-iterable NoneType" at format time
        # and breaks every access log line. Redacting msg + args separately keeps
        # both the standard ``msg % args`` path and arg-consuming formatters working.
        if isinstance(record.msg, str):
            record.msg = _redact_text(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                _redact_text(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        elif isinstance(record.args, dict):
            record.args = {
                key: (_redact_text(value) if isinstance(value, str) else value)
                for key, value in record.args.items()
            }

        # Scrub string values in structured extras (skip standard LogRecord attrs).
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_KEYS:
                continue
            if isinstance(value, str):
                record.__dict__[key] = _redact_text(value)

        # Pre-render and scrub the exception traceback so secrets in exception
        # messages / connection strings never reach the formatter unmasked.
        if record.exc_info:
            if record.exc_text is None:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = _redact_text(record.exc_text)
            record.exc_info = None
        if record.exc_text:
            record.exc_text = _redact_text(record.exc_text)
        return True


def setup_logging(level: str = "INFO") -> None:
    """루트 로거를 설정한다.

    Args:
        level: 로그 레벨 문자열.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn installs its own handlers and uvicorn.access uses propagate=False,
    # so the root handler's filter does not reach request access lines. Attach the
    # redaction filter directly to the uvicorn loggers so access/error logs are
    # masked too. Guarded so repeated setup_logging calls stay idempotent.
    for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        if not any(isinstance(existing, RedactingFilter) for existing in uvicorn_logger.filters):
            uvicorn_logger.addFilter(RedactingFilter())
