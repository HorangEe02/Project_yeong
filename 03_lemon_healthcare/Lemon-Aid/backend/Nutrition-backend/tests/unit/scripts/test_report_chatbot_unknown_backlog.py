"""Tests for the chatbot unknown backlog report script."""

from __future__ import annotations

import os

from scripts import report_chatbot_unknown_backlog as report


def test_report_args_default_to_all_unknown_backlog_groups() -> None:
    """Verify the operator report is not top-N limited by default."""
    args = report._parse_args(
        [
            "--database-url",
            "postgresql://postgres:secret@db.example.test:5432/postgres?sslmode=require",
        ]
    )

    assert args.row_limit is None
    assert args.group_limit is None
    assert args.env_file.name == ".env"
    assert args.status == "open"


def test_report_args_allow_explicit_limits_for_compact_views() -> None:
    """Verify compact dashboard-style reports can still request limits."""
    args = report._parse_args(
        [
            "--database-url",
            "postgresql://postgres:secret@db.example.test:5432/postgres?sslmode=require",
            "--row-limit",
            "100",
            "--group-limit",
            "10",
        ]
    )

    assert args.row_limit == 100
    assert args.group_limit == 10


def test_markdown_report_lists_every_payload_group() -> None:
    """Verify markdown rendering does not hide groups from the payload."""
    payload = {
        "total_groups": 2,
        "total_events": 3,
        "groups": [
            {
                "status": "open",
                "category": "nutrition_analysis",
                "primary_intent": "supplement",
                "missing_topic": "iron_food_candidates",
                "needed_evidence_type": "nutrition_reference",
                "retrieval_status": "no_match",
                "count": 2,
                "related_conditions": [],
                "retrieval_warnings": ["no_reviewed_answer_card"],
            },
            {
                "status": "open",
                "category": "medication_supplement_caution",
                "primary_intent": "medication",
                "missing_topic": "supplement_drug_interaction",
                "needed_evidence_type": "supplement_drug_interaction",
                "retrieval_status": "no_match",
                "count": 1,
                "related_conditions": [],
                "retrieval_warnings": ["no_reviewed_answer_card"],
            },
        ],
    }

    markdown = report._markdown_report(payload)

    assert "iron_food_candidates" in markdown
    assert "supplement_drug_interaction" in markdown
    assert "total_groups: 2" in markdown


def test_load_env_file_sets_missing_database_url(tmp_path, monkeypatch) -> None:
    """Verify scheduled reports can read backend/.env without exposing secrets."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://postgres:secret@db.example.test:5432/postgres?sslmode=require\n",
        encoding="utf-8",
    )

    try:
        report._load_env_file(env_file)

        assert os.environ["DATABASE_URL"].startswith("postgresql://postgres:")
    finally:
        os.environ.pop("DATABASE_URL", None)


def test_load_env_file_does_not_override_existing_env(tmp_path, monkeypatch) -> None:
    """Verify explicit scheduler environment values win over dotenv defaults."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://existing")
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://from-file\n", encoding="utf-8")

    report._load_env_file(env_file)

    assert os.environ["DATABASE_URL"] == "postgresql://existing"
