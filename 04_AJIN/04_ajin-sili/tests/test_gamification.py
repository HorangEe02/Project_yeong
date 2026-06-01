"""v4.7 C-4 — 게이미피케이션 단위 테스트.

배지 평가 + DB CRUD + 리더보드 산식.
모든 테스트는 임시 SQLite (tmp_path) 에서 격리 실행.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """gamification_db 의 DB_PATH 를 tmp 로 재할당."""
    db = tmp_path / "learning.db"
    monkeypatch.setattr("features.onboarding.gamification_db.DB_PATH", db)
    from features.onboarding import gamification_db as gdb

    gdb.init_gamification_db(db)
    return db


def test_init_creates_5_tables(tmp_db):
    conn = sqlite3.connect(str(tmp_db))
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    names = {r[0] for r in rows}
    conn.close()
    for required in [
        "quiz_attempts",
        "sop_progress",
        "user_badges",
        "user_daily_activity",
        "dept_leaderboard_snapshots",
    ]:
        assert required in names, f"missing table: {required}"


def test_quiz_starter_after_first_quiz(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    gdb.record_quiz_attempt("u1", is_correct=True, category="sop", difficulty="basic")
    newly = evaluate_badges("u1")
    assert "quiz_starter" in newly


def test_quiz_master_basic_at_10(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    # 정답 10개 누적
    for _ in range(10):
        gdb.record_quiz_attempt("u1", is_correct=True, category="sop", difficulty="basic")
    newly = evaluate_badges("u1")
    assert "quiz_master_basic" in newly
    # 두 번째 평가는 멱등 — 다시 반환되지 않음
    again = evaluate_badges("u1")
    assert "quiz_master_basic" not in again


def test_quiz_master_basic_not_unlocked_at_9(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    for _ in range(9):
        gdb.record_quiz_attempt("u1", is_correct=True, category="sop", difficulty="basic")
    newly = evaluate_badges("u1")
    assert "quiz_master_basic" not in newly


def test_quiz_master_advanced_at_5(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    for _ in range(5):
        gdb.record_quiz_attempt("u1", is_correct=True, category="sop", difficulty="advanced")
    newly = evaluate_badges("u1")
    assert "quiz_master_advanced" in newly


def test_helpful_voice_at_50(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    for _ in range(50):
        gdb.upsert_daily("u1", field="positive_feedback", delta=1)
    newly = evaluate_badges("u1")
    assert "helpful_voice" in newly


def test_glossary_native_at_100(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    gdb.upsert_daily("u1", field="glossary_lookups", delta=100)
    newly = evaluate_badges("u1")
    assert "glossary_native" in newly


def test_streak_7_consecutive_days(tmp_db, monkeypatch):
    from datetime import date, timedelta
    from features.onboarding import gamification_db as gdb

    # 직접 7일 row 삽입
    today = date.today()
    with gdb.get_conn() as conn:
        for i in range(7):
            d = (today - timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT INTO user_daily_activity (user_id, date, chat_count) VALUES (?, ?, 1)",
                ("u1", d),
            )
    assert gdb.count_streak_days("u1") >= 7


def test_streak_broken_returns_short(tmp_db):
    from datetime import date, timedelta
    from features.onboarding import gamification_db as gdb

    today = date.today()
    with gdb.get_conn() as conn:
        # 오늘 + 3일전 (gap 1일) → streak=1 (오늘만)
        conn.execute(
            "INSERT INTO user_daily_activity (user_id, date, chat_count) VALUES (?, ?, 1)",
            ("u1", today.isoformat()),
        )
        conn.execute(
            "INSERT INTO user_daily_activity (user_id, date, chat_count) VALUES (?, ?, 1)",
            ("u1", (today - timedelta(days=3)).isoformat()),
        )
    assert gdb.count_streak_days("u1") == 1


def test_sop_explorer_after_3_completed(tmp_db, monkeypatch):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    # 3개 SOP 각각 1단계만 있음으로 가정 (mocking sop_guide)
    class FakeStep:
        pass

    class FakeSop:
        def __init__(self, sop_id, n_steps, dept=""):
            self.sop_id = sop_id
            self.steps = [FakeStep() for _ in range(n_steps)]
            self.department = dept

    fakes = [
        FakeSop("S1", 2),
        FakeSop("S2", 2),
        FakeSop("S3", 2),
    ]
    monkeypatch.setattr("features.onboarding.sop_guide.get_all_sops", lambda: fakes)

    for sop_id in ["S1", "S2", "S3"]:
        gdb.record_sop_step("u1", sop_id, 1, "2025-01-01")
        gdb.record_sop_step("u1", sop_id, 2, "2025-01-01")

    newly = evaluate_badges("u1")
    assert "sop_explorer" in newly


def test_dept_leaderboard_hidden_when_less_than_3(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import compute_dept_leaderboard

    gdb.upsert_daily("u1", field="chat_count", delta=1, user_department="QA")
    gdb.upsert_daily("u2", field="chat_count", delta=1, user_department="QA")
    result = compute_dept_leaderboard("QA")
    assert result["visible"] is False
    assert result["total_active"] == 2
    assert result["top_users"] == []


def test_dept_leaderboard_visible_at_3(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import compute_dept_leaderboard

    for uid in ["u1", "u2", "u3"]:
        gdb.upsert_daily(uid, field="chat_count", delta=10, user_department="QA")
        gdb.upsert_daily(uid, field="quiz_correct", delta=1, user_department="QA")
    result = compute_dept_leaderboard("QA")
    assert result["visible"] is True
    assert len(result["top_users"]) == 3
    # u1~u3 동일 점수이므로 정확히 점수 검증
    expected = 10 * 1 + 1 * 10  # chat_count*1 + quiz_correct*10
    for u in result["top_users"]:
        assert u["score"] == expected


def test_weekly_score_formula(tmp_db):
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import compute_user_weekly_score

    gdb.upsert_daily("u1", field="quiz_correct", delta=2)
    gdb.upsert_daily("u1", field="sop_steps_completed", delta=3)
    gdb.upsert_daily("u1", field="positive_feedback", delta=4)
    gdb.upsert_daily("u1", field="chat_count", delta=5)
    # 2*10 + 3*5 + 4*3 + 5*1 = 20 + 15 + 12 + 5 = 52
    assert compute_user_weekly_score("u1") == 52


def test_persist_badge_is_idempotent(tmp_db):
    from features.onboarding import gamification_db as gdb

    first = gdb.persist_badge("u1", "quiz_starter")
    second = gdb.persist_badge("u1", "quiz_starter")
    assert first is True
    assert second is False
    earned = gdb.get_earned_badges("u1")
    assert len(earned) == 1
    assert earned[0]["badge_id"] == "quiz_starter"
