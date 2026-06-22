"""Unit tests for ``src.utils.logger`` PII redaction."""

from __future__ import annotations

import logging

from src.utils.logger import RedactingFilter, setup_logging


def _build_record(message: str) -> logging.LogRecord:
    """Construct a bare log record for filter assertion.

    Args:
        message: Message body to feed the filter.

    Returns:
        Log record carrying the message.
    """
    return logging.LogRecord(
        name="lemon-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=None,
        exc_info=None,
    )


def test_bearer_token_is_masked() -> None:
    """Verify Authorization-style bearer tokens are masked."""
    record = _build_record("auth Bearer eyJhbGciOiJSUzI1NiJ9.payload.signature")
    RedactingFilter().filter(record)
    assert record.getMessage() == "auth Bearer ***REDACTED***"


def test_email_is_masked() -> None:
    """Verify email addresses are replaced."""
    record = _build_record("from foo.bar@lemon.com to admin@x.io")
    RedactingFilter().filter(record)
    assert "foo.bar@lemon.com" not in record.getMessage()
    assert "admin@x.io" not in record.getMessage()
    assert "***EMAIL***" in record.getMessage()


def test_hex_hash_is_masked() -> None:
    """Verify long hex digests (sha256, owner_subject) are masked."""
    sha = "a" * 64
    record = _build_record(f"owner_subject={sha} status=ok")
    RedactingFilter().filter(record)
    assert sha not in record.getMessage()
    assert "***HASH***" in record.getMessage()


def test_setup_logging_attaches_redacting_filter() -> None:
    """Verify ``setup_logging`` installs a handler with the redaction filter."""
    setup_logging("INFO")
    root = logging.getLogger()
    handlers = root.handlers
    assert handlers, "setup_logging should install at least one handler"
    filters = [f for h in handlers for f in h.filters]
    assert any(isinstance(f, RedactingFilter) for f in filters)
