"""P4 D15 — 신입 학습경로 큐레이션.

흐름:
  1. 사수가 N주차 (default 4) 핵심 변경 list 를 신입에게 할당 (`curate_path`)
  2. 신입이 RAG 챗봇으로 학습 + 자동 mini 퀴즈 (객관식 3문항)
  3. 채점 → 진도 update + 오답 audit
  4. 완료 시 사수에게 1-클릭 평가 요청 (`request_mentor_review`)
  5. 사수 평가 (pass / redo / pass_with_comment) → 다음 주차 활성화

P1 D4 (regulation_qa) RAG + Slack notify 인프라 100% 재사용.
LLM 미연결 시 룰 폴백 — 단순 메타데이터(grade/dept) 만 묻는 객관식 자동 생성.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

VALID_REVIEW = {"pending", "pass", "redo", "pass_with_comment"}
DEFAULT_PASS_SCORE = 60


# ─────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────


def _conn() -> sqlite3.Connection:
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    c = sqlite3.connect(CHANGE_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ─────────────────────────────────────────────────────────────
# 큐레이션
# ─────────────────────────────────────────────────────────────


def curate_path(
    *,
    name: str,
    owner_employee_id: str,
    assignee_employee_id: str,
    week_split: list[list[int]],
    min_quiz_score: int = DEFAULT_PASS_SCORE,
) -> int:
    """사수가 신입에게 학습경로 할당.

    week_split: 주차별 change_id 그룹 — 예: [[10,11], [20,21,22], [30]] (3주)
    """
    if not week_split or not all(isinstance(w, list) for w in week_split):
        raise ValueError("week_split 은 list[list[int]] 이어야 합니다")

    curriculum = [
        {"week": i + 1, "change_ids": [int(c) for c in chs],
         "min_quiz_score": int(min_quiz_score)}
        for i, chs in enumerate(week_split)
    ]
    now = datetime.now().isoformat()

    c = _conn()
    cur = c.execute(
        """INSERT INTO learning_paths
           (name, owner_employee_id, assignee_employee_id, week_count,
            curriculum_json, status, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (
            name[:200],
            owner_employee_id[:100],
            assignee_employee_id[:100],
            len(curriculum),
            json.dumps(curriculum, ensure_ascii=False),
            "active",
            now,
        ),
    )
    path_id = int(cur.lastrowid)

    # progress row 생성 (모든 (week, change_id))
    for week_def in curriculum:
        for cid in week_def["change_ids"]:
            c.execute(
                """INSERT INTO learning_progress
                   (path_id, week, change_id, mentor_review, updated_at)
                   VALUES (?,?,?,?,?)""",
                (path_id, week_def["week"], cid, "pending", now),
            )
    c.commit()
    c.close()
    return path_id


def my_progress(employee_id: str) -> dict[str, Any]:
    """신입 본인 진도 — 활성 path 의 주차별 진도와 다음 액션."""
    c = _conn()
    paths = c.execute(
        """SELECT * FROM learning_paths
           WHERE assignee_employee_id = ? AND status = 'active'
           ORDER BY id DESC""",
        (employee_id,),
    ).fetchall()
    out = {"paths": []}
    for p in paths:
        try:
            curriculum = json.loads(p["curriculum_json"] or "[]")
        except json.JSONDecodeError:
            curriculum = []
        progress_rows = c.execute(
            "SELECT * FROM learning_progress WHERE path_id = ? ORDER BY week, id",
            (p["id"],),
        ).fetchall()
        items = [dict(r) for r in progress_rows]
        out["paths"].append({
            "id": p["id"],
            "name": p["name"],
            "owner_employee_id": p["owner_employee_id"],
            "week_count": p["week_count"],
            "curriculum": curriculum,
            "progress": items,
            "status": p["status"],
            "created_at": p["created_at"],
        })
    c.close()
    return out


def mentor_queue(owner_employee_id: str) -> list[dict[str, Any]]:
    """사수가 평가 대기 중인 progress row list."""
    c = _conn()
    rows = c.execute(
        """SELECT lp.*, paths.name as path_name, paths.assignee_employee_id
           FROM learning_progress lp
           JOIN learning_paths paths ON paths.id = lp.path_id
           WHERE paths.owner_employee_id = ?
             AND lp.mentor_review = 'pending'
             AND lp.quiz_score >= 0
           ORDER BY lp.updated_at DESC LIMIT 100""",
        (owner_employee_id,),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# 퀴즈 생성 (LLM → 룰 폴백)
# ─────────────────────────────────────────────────────────────


def _quiz_provider() -> str:
    return (os.environ.get("LEARNING_QUIZ_LLM_PROVIDER") or "").strip().lower()


def _generate_quiz_llm(change: dict[str, Any]) -> dict[str, Any] | None:
    """Ollama 호출 — 미연결/타임아웃 시 None.

    프롬프트로 객관식 1문항 + 3 choices + 정답 인덱스 JSON 요구.
    """
    provider = _quiz_provider()
    if provider in ("", "rule_only"):
        return None

    prompt = (
        "다음 규제 변경 요약을 보고 신입 사원 이해도 확인용 객관식 1문항을 만들어줘.\n"
        "응답은 반드시 JSON {\"question\": str, \"choices\": [str, str, str], "
        "\"answer_index\": 0|1|2} 형식만 사용.\n\n"
        f"제목: {change.get('item_title') or '(제목 없음)'}\n"
        f"요약: {change.get('summary_ko') or '(요약 없음)'}\n"
        f"등급: {change.get('grade') or 'MEDIUM'}\n"
        f"부서: {', '.join(change.get('affected_departments') or []) or '(미지정)'}\n"
    )
    try:
        from features.compliance.rag.regulation_qa import _call_llm
        text = _call_llm(prompt, timeout=10.0, feature="quiz_gen")
    except Exception as e:
        logger.debug("LLM 퀴즈 호출 실패: %s", e)
        return None
    if not text:
        return None
    # JSON 추출 (LLM 이 텍스트 wrapping 할 수 있음)
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    q = str(data.get("question") or "").strip()
    choices = data.get("choices") or []
    ans = data.get("answer_index")
    if (
        not q
        or not isinstance(choices, list)
        or len(choices) != 3
        or not isinstance(ans, int)
        or not 0 <= ans <= 2
    ):
        return None
    return {
        "question": q,
        "choices": [str(c)[:200] for c in choices],
        "answer_index": int(ans),
        "generated_by": "llm",
    }


def _generate_quiz_rule(change: dict[str, Any]) -> dict[str, Any]:
    """룰 폴백 — grade 또는 부서 메타만 묻는 객관식. 환각 위험 0."""
    grade = change.get("grade") or "MEDIUM"
    valid = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    distractors = [g for g in valid if g != grade][:2]
    choices = [grade] + distractors
    # 정답 위치 섞기 — change.id 로 deterministic
    cid = int(change.get("id") or change.get("change_id") or 0)
    answer_index = cid % 3
    rotated = choices[answer_index:] + choices[:answer_index]
    final = list(rotated)[:3]
    if grade not in final:
        final[0] = grade
    answer_index = final.index(grade)
    return {
        "question": (
            f"이 규제 변경의 등급은 무엇인가요? (제목: "
            f"{(change.get('item_title') or '제목없음')[:50]})"
        ),
        "choices": final,
        "answer_index": answer_index,
        "generated_by": "rule",
    }


def get_or_generate_quiz(change_id: int) -> dict[str, Any]:
    """캐시 우선. 없으면 LLM → 룰 폴백 으로 생성 후 저장.

    Returns: {question, choices, answer_index, generated_by, ...}
    """
    c = _conn()
    cached = c.execute(
        "SELECT * FROM learning_quiz WHERE change_id = ?", (change_id,)
    ).fetchone()
    if cached:
        d = dict(cached)
        try:
            d["choices"] = json.loads(d.pop("choices_json") or "[]")
        except json.JSONDecodeError:
            d["choices"] = []
        c.close()
        return d
    # change row 조회
    row = c.execute(
        """SELECT id, item_title, summary_ko, grade, affected_departments
           FROM regulation_changes WHERE id = ?""",
        (change_id,),
    ).fetchone()
    if row is None:
        c.close()
        raise ValueError(f"change_id={change_id} 미존재")
    change = dict(row)
    try:
        change["affected_departments"] = json.loads(
            change.get("affected_departments") or "[]"
        )
    except json.JSONDecodeError:
        change["affected_departments"] = []

    quiz = _generate_quiz_llm(change) or _generate_quiz_rule(change)
    now = datetime.now().isoformat()
    try:
        c.execute(
            """INSERT INTO learning_quiz
               (change_id, question, choices_json, answer_index, generated_by, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                change_id,
                quiz["question"][:500],
                json.dumps(quiz["choices"], ensure_ascii=False),
                int(quiz["answer_index"]),
                quiz["generated_by"],
                now,
            ),
        )
        c.commit()
    except sqlite3.IntegrityError:
        # 동시성 — 다른 호출이 이미 적재
        pass
    c.close()
    return {
        "change_id": change_id,
        "question": quiz["question"],
        "choices": quiz["choices"],
        "answer_index": quiz["answer_index"],
        "generated_by": quiz["generated_by"],
        "created_at": now,
    }


# ─────────────────────────────────────────────────────────────
# 채점
# ─────────────────────────────────────────────────────────────


def get_quiz_preview(progress_id: int) -> dict[str, Any]:
    """P4.1 §6 — 응시 전 미리보기. answer_index 미포함, take_quiz 사이드이펙트 없음."""
    c = _conn()
    prog = c.execute(
        "SELECT * FROM learning_progress WHERE id = ?", (progress_id,)
    ).fetchone()
    c.close()
    if prog is None:
        return {"ok": False, "error": f"progress_id={progress_id} 미존재"}
    quiz = get_or_generate_quiz(int(prog["change_id"]))
    return {
        "ok": True,
        "progress_id": progress_id,
        "change_id": int(prog["change_id"]),
        "question": quiz["question"],
        "choices": quiz["choices"],
        "generated_by": quiz["generated_by"],
        # answer_index 의도적으로 미포함
    }


def take_quiz(
    progress_id: int,
    choice_index: int,
    *,
    as_owner: bool = False,
) -> dict[str, Any]:
    """채점 + 진도 update.

    P4.1 §4 — owner 시뮬 응시는 `mentor_dryrun_score` 만 갱신. assignee 의 quiz_score /
    quiz_attempts 는 보호 (사수가 신입 점수 조작 불가).
    """
    c = _conn()
    prog = c.execute(
        "SELECT * FROM learning_progress WHERE id = ?", (progress_id,)
    ).fetchone()
    if prog is None:
        c.close()
        return {"ok": False, "error": f"progress_id={progress_id} 미존재"}

    quiz = get_or_generate_quiz(int(prog["change_id"]))
    correct = int(choice_index) == int(quiz["answer_index"])
    score = 100 if correct else 0
    now = datetime.now().isoformat()
    if as_owner:
        c.execute(
            """UPDATE learning_progress
               SET mentor_dryrun_score = ?, updated_at = ?
               WHERE id = ?""",
            (score, now, progress_id),
        )
    else:
        c.execute(
            """UPDATE learning_progress
               SET quiz_score = ?, quiz_attempts = quiz_attempts + 1,
                   read_at = COALESCE(NULLIF(read_at, ''), ?),
                   updated_at = ?
               WHERE id = ?""",
            (score, now, now, progress_id),
        )
    c.commit()
    c.close()
    return {
        "ok": True,
        "correct": correct,
        "score": score,
        "answer_index": quiz["answer_index"],
        "question": quiz["question"],
        "as_owner": bool(as_owner),
    }


# ─────────────────────────────────────────────────────────────
# 사수 평가
# ─────────────────────────────────────────────────────────────


def request_mentor_review(progress_id: int) -> dict[str, Any]:
    """사수에게 평가 요청 — Slack DM (notify_slack 재사용).

    progress.mentor_review 가 pending 으로 유지 (이미 그러함). Slack 만 발화.
    """
    c = _conn()
    row = c.execute(
        """SELECT lp.*, paths.name as path_name, paths.owner_employee_id,
                  rc.item_title as change_title
           FROM learning_progress lp
           JOIN learning_paths paths ON paths.id = lp.path_id
           LEFT JOIN regulation_changes rc ON rc.id = lp.change_id
           WHERE lp.id = ?""",
        (progress_id,),
    ).fetchone()
    c.close()
    if row is None:
        return {"ok": False, "error": f"progress_id={progress_id} 미존재"}

    sent = False
    try:
        from features.compliance.alerts.notify_slack import route as slack_route
        sent = slack_route({
            "grade": "INFO",
            "item_title": (
                f"📚 [학습 평가 요청] {row['path_name']} · "
                f"week {row['week']} · {row['change_title'] or ''}"
            ),
            "summary_ko": (
                f"신입 progress #{progress_id} 가 퀴즈를 마쳤습니다 (점수 {row['quiz_score']}). "
                f"평가를 부탁드립니다."
            ),
            "change_type": "learning_review",
            "affected_departments": [],
        }, change_id=int(row["change_id"]))
    except Exception as e:
        logger.warning("Slack 평가 요청 발송 실패 progress_id=%s: %s", progress_id, e)
    return {"ok": True, "slack_sent": bool(sent)}


def submit_review(
    progress_id: int,
    verdict: str,
    *,
    comment: str = "",
    reviewer: str = "",
) -> dict[str, Any]:
    """사수 평가 — pass / redo / pass_with_comment."""
    if verdict not in VALID_REVIEW or verdict == "pending":
        return {"ok": False, "error": f"invalid verdict (must be pass/redo/pass_with_comment)"}

    c = _conn()
    row = c.execute(
        "SELECT * FROM learning_progress WHERE id = ?", (progress_id,)
    ).fetchone()
    if row is None:
        c.close()
        return {"ok": False, "error": f"progress_id={progress_id} 미존재"}

    now = datetime.now().isoformat()
    c.execute(
        """UPDATE learning_progress
           SET mentor_review = ?, mentor_comment = ?, updated_at = ?
           WHERE id = ?""",
        (verdict, (comment or "")[:500], now, progress_id),
    )

    # path 의 모든 progress 가 pass / pass_with_comment 면 status='completed' 로 자동 전이
    path_id = int(row["path_id"])
    pending_or_redo = c.execute(
        """SELECT COUNT(*) FROM learning_progress
           WHERE path_id = ?
             AND mentor_review NOT IN ('pass','pass_with_comment')""",
        (path_id,),
    ).fetchone()[0]
    if pending_or_redo == 0:
        c.execute(
            "UPDATE learning_paths SET status = 'completed' WHERE id = ?",
            (path_id,),
        )

    c.commit()
    c.close()
    return {"ok": True, "verdict": verdict, "reviewer": reviewer}


# ─────────────────────────────────────────────────────────────
# 권한 체크
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# P5 §11 — 주관식 채점 (LLM rubric 기반, 룰 폴백)
# ─────────────────────────────────────────────────────────────


def _grade_short_answer_llm(
    question: str,
    user_answer: str,
    rubric: dict[str, Any],
) -> dict[str, Any] | None:
    """Ollama LLM 으로 주관식 채점. 미가용/타임아웃 시 None.

    rubric: {model_answer: str, key_points: list[str], max_score: int=100}
    응답: {"score": 0~max, "reason": str}
    """
    if _quiz_provider() in ("", "rule_only"):
        return None
    model_answer = (rubric or {}).get("model_answer") or ""
    key_points = (rubric or {}).get("key_points") or []
    max_score = int((rubric or {}).get("max_score") or 100)
    prompt = (
        "다음 신입 사원의 주관식 답변을 모범답안과 비교해 채점해주세요.\n"
        "응답은 반드시 JSON 만: {\"score\": 0~"
        f"{max_score}, \"reason\": \"한 줄 이유\"}}\n\n"
        f"질문: {question}\n"
        f"모범답안: {model_answer}\n"
        f"핵심 포인트: {', '.join(key_points)}\n"
        f"신입 답변: {user_answer}\n\n"
        f"채점 기준: 핵심 포인트 1개당 약 {max_score // max(1, len(key_points))}점, "
        "표현 다소 다르면 부분점수 인정."
    )
    try:
        from features.compliance.rag.regulation_qa import _call_llm
        text = _call_llm(prompt, timeout=15.0, feature="short_answer_grade")
    except Exception as e:
        logger.debug("LLM 주관식 채점 호출 실패: %s", e)
        return None
    if not text:
        return None
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    score = data.get("score")
    reason = str(data.get("reason") or "").strip()
    if not isinstance(score, (int, float)):
        return None
    score_int = max(0, min(int(round(score)), max_score))
    return {"score": score_int, "reason": reason or "LLM 채점", "generated_by": "llm"}


def _grade_short_answer_rule(
    question: str,
    user_answer: str,
    rubric: dict[str, Any],
) -> dict[str, Any]:
    """룰 폴백 — key_points 키워드 등장 비율 × max_score (deterministic, 환각 0)."""
    key_points = (rubric or {}).get("key_points") or []
    max_score = int((rubric or {}).get("max_score") or 100)
    if not key_points:
        return {"score": 0, "reason": "key_points 미설정 — 채점 불가", "generated_by": "rule"}
    answer_low = (user_answer or "").lower()
    hits = sum(1 for kp in key_points if str(kp).strip().lower() in answer_low)
    score = int(round(max_score * hits / max(1, len(key_points))))
    return {
        "score": score,
        "reason": f"핵심 키워드 {hits}/{len(key_points)} 매칭",
        "generated_by": "rule",
    }


def grade_short_answer(
    question: str,
    user_answer: str,
    rubric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """주관식 채점 — LLM 우선, 미가용 시 룰 폴백.

    Args:
      question: 질문
      user_answer: 신입 답변
      rubric: {model_answer, key_points: list[str], max_score: int=100}
    Returns: {score: 0~max_score, reason, generated_by}
    """
    rubric = rubric or {}
    user_answer = (user_answer or "").strip()
    if not user_answer:
        return {"score": 0, "reason": "빈 답변", "generated_by": "rule"}
    return (
        _grade_short_answer_llm(question, user_answer, rubric)
        or _grade_short_answer_rule(question, user_answer, rubric)
    )


def get_path_owner(path_id: int) -> str:
    c = _conn()
    row = c.execute(
        "SELECT owner_employee_id FROM learning_paths WHERE id = ?", (path_id,)
    ).fetchone()
    c.close()
    return row["owner_employee_id"] if row else ""


def get_progress_path_id(progress_id: int) -> int:
    c = _conn()
    row = c.execute(
        "SELECT path_id FROM learning_progress WHERE id = ?", (progress_id,)
    ).fetchone()
    c.close()
    return int(row["path_id"]) if row else 0
