"""Feature B draft approval workflow hardening tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from textwrap import dedent

from features.draft.version_db import approve_version, reject_version, submit_for_review


def _make_version_db(tmp_path: Path) -> Path:
    """Create an isolated version DB with review-workflow rows.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Path: SQLite database path.
    """

    db_path = tmp_path / "draft_versions.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        dedent(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                author TEXT DEFAULT '',
                department TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                version_num INTEGER NOT NULL DEFAULT 1,
                template_vars_json TEXT DEFAULT '{}',
                rendered_text TEXT DEFAULT '',
                change_summary TEXT DEFAULT '',
                created_at TEXT,
                created_by TEXT,
                status TEXT DEFAULT 'draft',
                reviewer_id TEXT DEFAULT '',
                reviewed_at TEXT DEFAULT '',
                review_note TEXT DEFAULT ''
            );
            INSERT INTO documents (id, doc_type, title, author) VALUES
                (1, 'oem_email', 'draft only', 'kim'),
                (2, 'oem_email', 'review ready', 'kim'),
                (3, 'oem_email', 'admin override', 'kim'),
                (4, 'oem_email', 'self review', 'kim'),
                (5, 'oem_email', 'reject ready', 'kim');
            INSERT INTO versions (id, document_id, status, reviewer_id, created_by) VALUES
                (10, 1, 'draft', '', 'kim'),
                (20, 2, 'under_review', 'park', 'kim'),
                (30, 3, 'under_review', 'park', 'kim'),
                (40, 4, 'under_review', 'kim', 'kim'),
                (50, 5, 'under_review', 'park', 'kim');
            """
        )
    )
    conn.commit()
    conn.close()
    return db_path


def test_draft_cannot_be_approved_directly(tmp_path: Path) -> None:
    """A version must be submitted before approval."""

    db_path = _make_version_db(tmp_path)

    assert approve_version(10, "park", db_path=db_path) is None


def test_assigned_reviewer_can_approve_under_review(tmp_path: Path) -> None:
    """The assigned reviewer can approve an under-review version."""

    db_path = _make_version_db(tmp_path)

    result = approve_version(20, "park", note="ok", db_path=db_path)

    assert result is not None
    assert result["status"] == "approved"
    assert result["reviewer_id"] == "park"


def test_author_cannot_submit_to_self_or_approve_self(tmp_path: Path) -> None:
    """Self-review is blocked before and during approval."""

    db_path = _make_version_db(tmp_path)

    assert submit_for_review(10, "kim", db_path=db_path) is None
    assert approve_version(40, "kim", db_path=db_path, allow_reviewer_override=True) is None


def test_l5_override_can_replace_reviewer_for_other_author(tmp_path: Path) -> None:
    """Admin override is supported at the service boundary for non-self approval."""

    db_path = _make_version_db(tmp_path)

    result = approve_version(
        30,
        "sysadmin",
        note="[L5 override by sysadmin]",
        db_path=db_path,
        allow_reviewer_override=True,
    )

    assert result is not None
    assert result["status"] == "approved"
    assert result["reviewer_id"] == "sysadmin"
    assert "L5 override" in result["review_note"]


def test_assigned_reviewer_can_reject_under_review(tmp_path: Path) -> None:
    """The assigned reviewer can reject an under-review version."""

    db_path = _make_version_db(tmp_path)

    result = reject_version(50, "park", note="needs edits", db_path=db_path)

    assert result is not None
    assert result["status"] == "rejected"
    assert result["review_note"] == "needs edits"

