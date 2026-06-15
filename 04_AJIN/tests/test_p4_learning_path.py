"""P4 D15 — 신입 학습경로 단위 테스트."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()
    return cd


@pytest.fixture(autouse=True)
def _no_external(monkeypatch):
    import config
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "", raising=False)
    # 룰 폴백 강제 (LLM 미사용)
    monkeypatch.setenv("LEARNING_QUIZ_LLM_PROVIDER", "rule_only")


def _seed_change(cd_module, **fields):
    conn = sqlite3.connect(cd_module.CHANGE_DB_PATH)
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO regulation_changes
           (detected_at, regulation_type, change_type, item_id, item_title,
            old_value, new_value, severity, status, grade, summary_ko,
            affected_departments, affected_plants, legal_class, penalty_severity_krw_mn)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            now, fields.get("regulation_type", "test"),
            fields.get("change_type", "added"),
            fields.get("item_id", "X1"),
            fields.get("item_title", "테스트 변경"),
            "", "", "info",
            fields.get("status", "pending"),
            fields.get("grade", "MEDIUM"),
            fields.get("summary_ko", "요약"),
            json.dumps(fields.get("affected_departments", []), ensure_ascii=False),
            "[]", "[]", 0,
        ),
    )
    conn.commit()
    cid = int(cur.lastrowid)
    conn.close()
    return cid


# ─────────────────────────────────────────────────────────────
# 큐레이션
# ─────────────────────────────────────────────────────────────


class TestCurate:
    def test_curate_creates_progress_rows(self, tmp_db):
        from features.compliance.learning_path import curate_path, my_progress
        c1 = _seed_change(tmp_db, item_title="A")
        c2 = _seed_change(tmp_db, item_title="B")
        c3 = _seed_change(tmp_db, item_title="C")

        pid = curate_path(
            name="신입 1주차",
            owner_employee_id="MENTOR1",
            assignee_employee_id="ROOKIE1",
            week_split=[[c1, c2], [c3]],
            min_quiz_score=60,
        )
        assert pid >= 1

        out = my_progress("ROOKIE1")
        assert len(out["paths"]) == 1
        path = out["paths"][0]
        assert path["week_count"] == 2
        assert len(path["progress"]) == 3
        weeks = sorted({p["week"] for p in path["progress"]})
        assert weeks == [1, 2]

    def test_invalid_week_split_raises(self, tmp_db):
        from features.compliance.learning_path import curate_path
        with pytest.raises(ValueError):
            curate_path(
                name="x", owner_employee_id="M", assignee_employee_id="R",
                week_split=[],
            )

    def test_my_progress_isolates_per_assignee(self, tmp_db):
        from features.compliance.learning_path import curate_path, my_progress
        c1 = _seed_change(tmp_db)
        curate_path(name="p1", owner_employee_id="M", assignee_employee_id="A1",
                    week_split=[[c1]])
        curate_path(name="p2", owner_employee_id="M", assignee_employee_id="A2",
                    week_split=[[c1]])
        a1 = my_progress("A1")
        a2 = my_progress("A2")
        assert len(a1["paths"]) == 1
        assert len(a2["paths"]) == 1
        assert a1["paths"][0]["name"] == "p1"
        assert a2["paths"][0]["name"] == "p2"


# ─────────────────────────────────────────────────────────────
# 퀴즈 (룰 폴백)
# ─────────────────────────────────────────────────────────────


class TestQuiz:
    def test_quiz_rule_fallback(self, tmp_db):
        from features.compliance.learning_path import get_or_generate_quiz
        cid = _seed_change(tmp_db, grade="LOW", item_title="테스트 변경 X")
        quiz = get_or_generate_quiz(cid)
        assert quiz["generated_by"] == "rule"
        assert len(quiz["choices"]) == 3
        assert 0 <= quiz["answer_index"] <= 2
        # 정답이 LOW (grade) 인지 확인
        assert quiz["choices"][quiz["answer_index"]] == "LOW"

    def test_quiz_cached_on_second_call(self, tmp_db):
        from features.compliance.learning_path import get_or_generate_quiz
        cid = _seed_change(tmp_db, grade="HIGH")
        q1 = get_or_generate_quiz(cid)
        q2 = get_or_generate_quiz(cid)
        assert q1["question"] == q2["question"]
        assert q1["choices"] == q2["choices"]

    def test_take_quiz_correct(self, tmp_db):
        from features.compliance.learning_path import (
            curate_path, take_quiz, get_or_generate_quiz, my_progress,
        )
        cid = _seed_change(tmp_db, grade="LOW")
        pid = curate_path(name="p", owner_employee_id="M",
                          assignee_employee_id="R", week_split=[[cid]])
        quiz = get_or_generate_quiz(cid)
        prog = my_progress("R")["paths"][0]["progress"][0]
        out = take_quiz(prog["id"], quiz["answer_index"])
        assert out["ok"] is True
        assert out["correct"] is True
        assert out["score"] == 100

    def test_take_quiz_wrong(self, tmp_db):
        from features.compliance.learning_path import (
            curate_path, take_quiz, get_or_generate_quiz, my_progress,
        )
        cid = _seed_change(tmp_db, grade="LOW")
        pid = curate_path(name="p", owner_employee_id="M",
                          assignee_employee_id="R", week_split=[[cid]])
        quiz = get_or_generate_quiz(cid)
        wrong = (quiz["answer_index"] + 1) % 3
        prog = my_progress("R")["paths"][0]["progress"][0]
        out = take_quiz(prog["id"], wrong)
        assert out["correct"] is False
        assert out["score"] == 0
        # attempts 가 증가했는지 확인
        again = my_progress("R")["paths"][0]["progress"][0]
        assert again["quiz_attempts"] == 1


# ─────────────────────────────────────────────────────────────
# 사수 평가
# ─────────────────────────────────────────────────────────────


class TestMentorReview:
    def test_pass_completes_path(self, tmp_db):
        from features.compliance.learning_path import (
            curate_path, get_or_generate_quiz, my_progress, submit_review,
            take_quiz,
        )
        c1 = _seed_change(tmp_db, grade="LOW")
        pid = curate_path(name="p", owner_employee_id="M",
                          assignee_employee_id="R", week_split=[[c1]])
        quiz = get_or_generate_quiz(c1)
        prog = my_progress("R")["paths"][0]["progress"][0]
        take_quiz(prog["id"], quiz["answer_index"])
        result = submit_review(prog["id"], "pass", comment="잘했음", reviewer="M")
        assert result["ok"] is True
        # 모든 progress pass → path completed
        c = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT status FROM learning_paths WHERE id = ?", (pid,)).fetchone()
        c.close()
        assert row["status"] == "completed"

    def test_redo_keeps_active(self, tmp_db):
        from features.compliance.learning_path import (
            curate_path, get_or_generate_quiz, my_progress, submit_review,
            take_quiz,
        )
        c1 = _seed_change(tmp_db, grade="LOW")
        pid = curate_path(name="p", owner_employee_id="M",
                          assignee_employee_id="R", week_split=[[c1]])
        quiz = get_or_generate_quiz(c1)
        prog = my_progress("R")["paths"][0]["progress"][0]
        wrong = (quiz["answer_index"] + 1) % 3
        take_quiz(prog["id"], wrong)
        out = submit_review(prog["id"], "redo", reviewer="M")
        assert out["ok"] is True
        c = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT status FROM learning_paths WHERE id = ?", (pid,)).fetchone()
        c.close()
        assert row["status"] == "active"
        # 신입은 다시 응시 가능 (mentor_review='redo' 라도 quiz_attempts 누적)
        take_quiz(prog["id"], quiz["answer_index"])
        again = my_progress("R")["paths"][0]["progress"][0]
        assert again["quiz_attempts"] == 2

    def test_invalid_verdict_rejected(self, tmp_db):
        from features.compliance.learning_path import (
            curate_path, my_progress, submit_review,
        )
        c1 = _seed_change(tmp_db)
        pid = curate_path(name="p", owner_employee_id="M",
                          assignee_employee_id="R", week_split=[[c1]])
        prog = my_progress("R")["paths"][0]["progress"][0]
        out = submit_review(prog["id"], "approved", reviewer="M")
        assert out["ok"] is False

    def test_grade_short_answer_rule_fallback_full_score(self, tmp_db):
        """P5 §11 — LLM 미가용 + 모든 key_point 등장 → 만점."""
        from features.compliance.learning_path import grade_short_answer
        out = grade_short_answer(
            question="REACH 의 SVHC 정의?",
            user_answer="EU REACH 규정의 SVHC — 고위험 화학물질로 1% 이상 함유 시 신고",
            rubric={
                "model_answer": "EU REACH 의 SVHC (Substances of Very High Concern)",
                "key_points": ["SVHC", "EU", "REACH"],
                "max_score": 100,
            },
        )
        assert out["score"] == 100
        assert out["generated_by"] == "rule"

    def test_grade_short_answer_partial_credit(self, tmp_db):
        from features.compliance.learning_path import grade_short_answer
        out = grade_short_answer(
            question="x",
            user_answer="EU 만 언급",
            rubric={"key_points": ["SVHC", "EU", "REACH"], "max_score": 100},
        )
        assert out["score"] == 33  # 1/3 * 100
        assert out["generated_by"] == "rule"

    def test_grade_short_answer_empty_returns_zero(self, tmp_db):
        from features.compliance.learning_path import grade_short_answer
        out = grade_short_answer("q", "", rubric={"key_points": ["A"]})
        assert out["score"] == 0

    def test_grade_short_answer_deterministic(self, tmp_db):
        """동일 (rubric, answer) 입력 → 동일 결과 (룰 폴백 deterministic 보장)."""
        from features.compliance.learning_path import grade_short_answer
        kwargs = dict(
            question="q", user_answer="EU REACH",
            rubric={"key_points": ["EU", "REACH", "SVHC"], "max_score": 90},
        )
        a = grade_short_answer(**kwargs)
        b = grade_short_answer(**kwargs)
        assert a == b

    def test_quiz_preview_omits_answer_index(self, tmp_db):
        """P4.1 §6 — preview 가 answer_index 없이 question/choices 만 반환, sideeffect 없음."""
        from features.compliance.learning_path import (
            curate_path, get_or_generate_quiz, get_quiz_preview, my_progress,
        )
        c1 = _seed_change(tmp_db, grade="LOW")
        curate_path(name="p", owner_employee_id="O",
                    assignee_employee_id="R", week_split=[[c1]])
        prog = my_progress("R")["paths"][0]["progress"][0]
        # 미리 quiz 생성
        get_or_generate_quiz(c1)
        out = get_quiz_preview(prog["id"])
        assert out["ok"] is True
        assert "answer_index" not in out
        assert isinstance(out["choices"], list) and len(out["choices"]) == 3
        # quiz_score / quiz_attempts 변화 없음
        again = my_progress("R")["paths"][0]["progress"][0]
        assert again["quiz_score"] == -1
        assert again["quiz_attempts"] == 0

    def test_owner_quiz_isolated_from_assignee(self, tmp_db):
        """P4.1 §4 — owner 응시는 mentor_dryrun_score 만, assignee 점수 보호."""
        from features.compliance.learning_path import (
            curate_path, get_or_generate_quiz, my_progress, take_quiz,
        )
        c1 = _seed_change(tmp_db, grade="LOW")
        curate_path(name="p", owner_employee_id="OWNER",
                    assignee_employee_id="ROOKIE", week_split=[[c1]])
        quiz = get_or_generate_quiz(c1)
        prog = my_progress("ROOKIE")["paths"][0]["progress"][0]

        # owner 가 (정답으로) 응시 → mentor_dryrun_score 만 갱신
        out_owner = take_quiz(prog["id"], quiz["answer_index"], as_owner=True)
        assert out_owner["correct"] is True
        assert out_owner["as_owner"] is True

        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT quiz_score, quiz_attempts, mentor_dryrun_score "
            "FROM learning_progress WHERE id = ?",
            (prog["id"],),
        ).fetchone()
        conn.close()
        # assignee 점수 / 시도 횟수는 변하지 않음
        assert row["quiz_score"] == -1
        assert row["quiz_attempts"] == 0
        # owner 점수는 별도 컬럼에 100 (정답)
        assert row["mentor_dryrun_score"] == 100

        # 그 다음 assignee 응시 (오답) → quiz_score=0, attempts=1, dryrun_score 유지
        wrong = (quiz["answer_index"] + 1) % 3
        take_quiz(prog["id"], wrong, as_owner=False)
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        conn.row_factory = sqlite3.Row
        row2 = conn.execute(
            "SELECT quiz_score, quiz_attempts, mentor_dryrun_score "
            "FROM learning_progress WHERE id = ?",
            (prog["id"],),
        ).fetchone()
        conn.close()
        assert row2["quiz_score"] == 0
        assert row2["quiz_attempts"] == 1
        assert row2["mentor_dryrun_score"] == 100  # 유지

    def test_anonymous_user_cannot_take_quiz(self, tmp_db):
        """P4 D15 fix #3 — me 가 빈 문자열인 user 는 RBAC 우회 불가."""
        import asyncio
        from fastapi import HTTPException
        from features.compliance.learning_path import curate_path, my_progress
        from backend.routers.compliance import (
            take_learning_quiz, submit_learning_review,
        )
        from backend.schemas.compliance import (
            LearningQuizRequest, LearningReviewRequest,
        )

        c1 = _seed_change(tmp_db, grade="LOW")
        curate_path(name="p", owner_employee_id="OWNER",
                    assignee_employee_id="ROOKIE", week_split=[[c1]])
        prog = my_progress("ROOKIE")["paths"][0]["progress"][0]

        class _AnonUser:
            employee_id = ""
            email = ""

        # quiz: 빈 me 는 403
        with pytest.raises(HTTPException) as exc:
            asyncio.get_event_loop().run_until_complete(
                take_learning_quiz(prog["id"],
                                   LearningQuizRequest(choice_index=0),
                                   user=_AnonUser()),
            )
        assert exc.value.status_code == 403

        # review: 빈 me 는 403
        with pytest.raises(HTTPException) as exc:
            asyncio.get_event_loop().run_until_complete(
                submit_learning_review(
                    prog["id"],
                    LearningReviewRequest(verdict="pass", comment=""),
                    user=_AnonUser(),
                ),
            )
        assert exc.value.status_code == 403

    def test_mentor_queue(self, tmp_db):
        from features.compliance.learning_path import (
            curate_path, get_or_generate_quiz, mentor_queue,
            my_progress, take_quiz,
        )
        c1 = _seed_change(tmp_db, grade="LOW", item_title="P15-1")
        pid = curate_path(name="p", owner_employee_id="MENTOR_X",
                          assignee_employee_id="R", week_split=[[c1]])
        quiz = get_or_generate_quiz(c1)
        prog = my_progress("R")["paths"][0]["progress"][0]
        take_quiz(prog["id"], quiz["answer_index"])
        q = mentor_queue("MENTOR_X")
        assert len(q) == 1
        assert q[0]["path_name"] == "p"
        assert q[0]["assignee_employee_id"] == "R"
        # 평가 제출 후엔 queue 에서 빠짐
        from features.compliance.learning_path import submit_review
        submit_review(prog["id"], "pass", reviewer="MENTOR_X")
        q2 = mentor_queue("MENTOR_X")
        assert q2 == []
