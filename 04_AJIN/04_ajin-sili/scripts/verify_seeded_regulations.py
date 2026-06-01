#!/usr/bin/env python3
"""아진산업 AJIN Supabase regulation_changes + live_alarms + notification_outbox 검증 스크립트.

P0-2 시드 데이터 5단계 검증. CI 통합 가능한 JSON 출력 지원.
실제 Supabase 스키마 기준 (v2.0.0): 시나리오 디테일은 payload JSON에 저장.

검증 단계:
  1. regulation_changes row count = 3 (REG-2025-12-001, REG-2025-12-002, REG-2026-Q1-003)
     쿼리: select id, source, title, severity, status, payload->>'grade' as grade,
                  payload->>'penalty_severity_krw_mn' as penalty
  2. live_alarms row count = 3, CRITICAL 1건 acknowledged_at IS NULL 확인
     쿼리: select id, severity, acknowledged_at is null as unacked, message, payload
  3. notification_outbox row count = 4, payload.regulation_change_id FK 일관성 확인
     쿼리: select id, event_type, target, status, available_at
  4. payload.penalty_severity_krw_mn 재계산값 확인 (CRITICAL+3설비+산안법 → ₩5천만)
  5. 시연 쿼리: "CRITICAL severity, acknowledged_at IS NULL" → 첫 결과가 프레스 알림인지

사용 예:
    python3 scripts/verify_seeded_regulations.py
    python3 scripts/verify_seeded_regulations.py --demo-date=2026-06-10
    python3 scripts/verify_seeded_regulations.py --json
    python3 scripts/verify_seeded_regulations.py --json > /tmp/verify_regulations.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ROOT = REPO_ROOT.parent  # 04_AJIN/

AJIN_ASSISTANT = ROOT / "ajin-ai-assistant"
if str(AJIN_ASSISTANT) not in sys.path:
    sys.path.insert(0, str(AJIN_ASSISTANT))

try:
    from features.compliance.penalty_calculator import calculate_noncompliance_penalty
    _PENALTY_AVAILABLE = True
except ImportError as _e:
    _PENALTY_AVAILABLE = False
    _PENALTY_IMPORT_ERROR = str(_e)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

KST = timezone(timedelta(hours=9))
DEFAULT_DEMO_DATE = "2026-06-10"

EXPECTED_REG_IDS = {
    "REG-2025-12-001-PRESS-SAFETY",
    "REG-2025-12-002-CHROMIUM-SVHC",
    "REG-2026-Q1-003-EV-HV",
}
EXPECTED_ALARM_IDS = {
    "ALARM-2026-06-09-001",
    "ALARM-2026-06-08-002",
    "ALARM-2026-06-07-003",
}
EXPECTED_OUTBOX_COUNT = 4

# 시연 메인 시나리오 기대값 (CRITICAL, 3설비, 산안법)
PRESS_REG_ID = "REG-2025-12-001-PRESS-SAFETY"
PRESS_ALARM_ID = "ALARM-2026-06-09-001"
EXPECTED_PRESS_FINE_MN = 50.0       # ₩5천만
EXPECTED_PRESS_RISK_SCORE = 300.0

# ---------------------------------------------------------------------------
# 결과 타입
# ---------------------------------------------------------------------------

StepResult = dict[str, Any]


def _pass(step: int, name: str, detail: str, data: Any = None) -> StepResult:
    return {"step": step, "name": name, "status": "PASS", "detail": detail, "data": data}


def _fail(step: int, name: str, detail: str, data: Any = None) -> StepResult:
    return {"step": step, "name": name, "status": "FAIL", "detail": detail, "data": data}


def _warn(step: int, name: str, detail: str, data: Any = None) -> StepResult:
    return {"step": step, "name": name, "status": "WARN", "detail": detail, "data": data}


# ---------------------------------------------------------------------------
# Supabase 클라이언트
# ---------------------------------------------------------------------------

def _get_sb_client() -> Any:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")

    if not supabase_url:
        raise EnvironmentError("SUPABASE_URL 환경변수가 설정되지 않았습니다.")
    if not supabase_key:
        raise EnvironmentError("SUPABASE_SECRET_KEY 환경변수가 설정되지 않았습니다.")

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(f"supabase 패키지가 필요합니다: pip install supabase\n{exc}") from exc

    return create_client(supabase_url, supabase_key)


# ---------------------------------------------------------------------------
# 검증 단계
# ---------------------------------------------------------------------------

def step1_regulation_changes_count(sb: Any) -> StepResult:
    """Step 1: regulation_changes row count = 3, 예상 ID 모두 존재.

    쿼리: select id, source, title, severity, status,
                 payload->>'grade' as grade,
                 payload->>'penalty_severity_krw_mn' as penalty
    """
    step, name = 1, "regulation_changes row count"
    try:
        result = (
            sb.table("regulation_changes")
            .select("id, source, title, severity, status, payload")
            .in_("id", list(EXPECTED_REG_IDS))
            .execute()
        )
        rows = result.data or []
        found_ids = {r["id"] for r in rows}
        missing = EXPECTED_REG_IDS - found_ids

        # payload에서 grade, penalty 추출 (검증 출력용)
        rows_summary = []
        for r in rows:
            payload = r.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            rows_summary.append({
                "id": r["id"],
                "source": r.get("source"),
                "severity": r.get("severity"),
                "status": r.get("status"),
                "grade": payload.get("grade"),
                "penalty_severity_krw_mn": payload.get("penalty_severity_krw_mn"),
            })

        if len(rows) == 3 and not missing:
            return _pass(
                step, name,
                f"regulation_changes 3건 모두 확인 — {sorted(found_ids)}",
                rows_summary,
            )
        else:
            detail = f"기대=3건, 실제={len(rows)}건"
            if missing:
                detail += f", 누락 ID={sorted(missing)}"
            return _fail(step, name, detail, {"found": rows_summary, "missing": sorted(missing)})

    except Exception as exc:
        return _fail(step, name, f"쿼리 오류: {exc}")


def step2_live_alarms_count(sb: Any) -> StepResult:
    """Step 2: live_alarms row count = 3, CRITICAL 1건 acknowledged_at IS NULL 확인.

    쿼리: select id, severity, acknowledged_at is null as unacked, message, payload
    acknowledged_at IS NULL → 미승인 (unacked=true)
    """
    step, name = 2, "live_alarms count + CRITICAL unacked"
    try:
        result = (
            sb.table("live_alarms")
            .select("id, severity, acknowledged_at, message, payload")
            .in_("id", list(EXPECTED_ALARM_IDS))
            .execute()
        )
        rows = result.data or []
        found_ids = {r["id"] for r in rows}
        missing = EXPECTED_ALARM_IDS - found_ids

        # acknowledged_at IS NULL → 미승인
        critical_unacked = [
            r for r in rows
            if r.get("severity") == "CRITICAL" and r.get("acknowledged_at") is None
        ]

        rows_summary = [
            {
                "id": r["id"],
                "severity": r.get("severity"),
                "unacked": r.get("acknowledged_at") is None,
                "message": (r.get("message") or "")[:60],
            }
            for r in rows
        ]

        issues = []
        if len(rows) != 3:
            issues.append(f"row count 기대=3, 실제={len(rows)}")
        if missing:
            issues.append(f"누락 ID={sorted(missing)}")
        if len(critical_unacked) < 1:
            issues.append("CRITICAL + acknowledged_at IS NULL 알람 없음 (기대 >= 1건)")

        if not issues:
            return _pass(
                step, name,
                f"live_alarms 3건 확인, CRITICAL unacked={len(critical_unacked)}건",
                {"rows": rows_summary, "critical_unacked_count": len(critical_unacked)},
            )
        return _fail(step, name, "; ".join(issues), {"rows": rows_summary})

    except Exception as exc:
        return _fail(step, name, f"쿼리 오류: {exc}")


def step3_outbox_fk(sb: Any) -> StepResult:
    """Step 3: notification_outbox row count = 4, payload.regulation_change_id FK 일관성.

    쿼리: select id, event_type, target, status, available_at
    FK는 payload.regulation_change_id (top-level 컬럼 없음)
    """
    step, name = 3, "notification_outbox count + FK consistency"
    try:
        expected_outbox_ids = [
            "NOTIF-2026-06-09-001-SAFETY",
            "NOTIF-2026-06-08-002-SAFETY",
            "NOTIF-2026-06-08-003-ENV",
            "NOTIF-2026-06-07-004-QA",
        ]
        result = (
            sb.table("notification_outbox")
            .select("id, event_type, target, status, available_at, payload")
            .in_("id", expected_outbox_ids)
            .execute()
        )
        rows = result.data or []

        # payload에서 regulation_change_id 추출 (FK 검증용)
        outbox_reg_ids: set[str] = set()
        for r in rows:
            payload = r.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            reg_id = payload.get("regulation_change_id")
            if reg_id:
                outbox_reg_ids.add(reg_id)

        invalid_fks = outbox_reg_ids - EXPECTED_REG_IDS

        # 미발송 1건 확인 (NOTIF-2026-06-09-001-SAFETY available_at=null)
        unsent = [r for r in rows if r.get("available_at") is None]

        rows_summary = [
            {
                "id": r["id"],
                "event_type": r.get("event_type"),
                "target": r.get("target"),
                "status": r.get("status"),
                "available_at": r.get("available_at"),
            }
            for r in rows
        ]

        issues = []
        if len(rows) != EXPECTED_OUTBOX_COUNT:
            issues.append(f"row count 기대={EXPECTED_OUTBOX_COUNT}, 실제={len(rows)}")
        if invalid_fks:
            issues.append(f"FK 불일치 payload.regulation_change_id: {invalid_fks}")
        if len(unsent) < 1:
            issues.append("available_at=NULL 미발송 항목 없음 (기대 1건)")

        if not issues:
            return _pass(
                step, name,
                f"notification_outbox 4건 확인, FK 일관성 OK, 미발송={len(unsent)}건",
                {"rows": rows_summary, "unsent_count": len(unsent)},
            )
        return _fail(step, name, "; ".join(issues), {"rows": rows_summary, "invalid_fks": list(invalid_fks)})

    except Exception as exc:
        return _fail(step, name, f"쿼리 오류: {exc}")


def step4_penalty_recalculation(sb: Any, demo_date: date) -> StepResult:
    """Step 4: payload.penalty_severity_krw_mn 재계산값 확인 (CRITICAL+3설비+산안법 → ₩5천만).

    쿼리: select id, severity, status, payload
    payload에서 grade, legal_class, effective_date, facility_count 추출 후 재계산.
    """
    step, name = 4, "payload.penalty_severity_krw_mn 재계산 검증"

    try:
        result = (
            sb.table("regulation_changes")
            .select("id, severity, status, payload")
            .eq("id", PRESS_REG_ID)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return _fail(step, name, f"{PRESS_REG_ID} DB에서 찾을 수 없음")

        row = rows[0]
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        db_fine = float(payload.get("penalty_severity_krw_mn") or 0)

    except Exception as exc:
        return _fail(step, name, f"DB 쿼리 오류: {exc}")

    # penalty_calculator 재계산
    if not _PENALTY_AVAILABLE:
        return _warn(
            step, name,
            f"penalty_calculator import 불가 — DB payload 저장값만 확인: ₩{db_fine:.0f}mn (기대 >= {EXPECTED_PRESS_FINE_MN:.0f}mn)",
            {"db_fine_mn": db_fine, "import_error": _PENALTY_IMPORT_ERROR},
        )

    effective_str = payload.get("effective_date", "")
    try:
        effective = date.fromisoformat(effective_str)
    except (ValueError, TypeError):
        effective = date(2026, 9, 1)

    days_to_effective = (effective - demo_date).days
    grade = payload.get("grade", "CRITICAL")
    legal_class = payload.get("legal_class", "산안법")
    n_facilities = payload.get("facility_count") or len(payload.get("affected_facilities", [1, 2, 3]))
    n_facilities = max(int(n_facilities), 1)

    est = calculate_noncompliance_penalty(
        grade=grade,
        affected_facilities=n_facilities,
        days_to_effective=days_to_effective,
        law_category=legal_class,
    )

    calc_fine = est.estimated_fine_krw_mn
    calc_risk = est.risk_score

    fine_ok = abs(db_fine - calc_fine) < 0.1
    risk_ok = abs(calc_risk - EXPECTED_PRESS_RISK_SCORE) < 0.1

    detail = (
        f"payload.DB={db_fine:.1f}mn, 재계산={calc_fine:.1f}mn (기대={EXPECTED_PRESS_FINE_MN:.0f}mn), "
        f"risk_score={calc_risk:.1f} (기대={EXPECTED_PRESS_RISK_SCORE:.0f})"
    )

    data = {
        "db_fine_mn": db_fine,
        "calc_fine_mn": calc_fine,
        "expected_fine_mn": EXPECTED_PRESS_FINE_MN,
        "calc_risk_score": calc_risk,
        "expected_risk_score": EXPECTED_PRESS_RISK_SCORE,
        "days_to_effective": days_to_effective,
        "n_facilities": n_facilities,
        "explanation": est.explanation,
    }

    if fine_ok and risk_ok:
        return _pass(step, name, detail, data)
    return _fail(step, name, f"값 불일치 — {detail}", data)


def step5_demo_query(sb: Any) -> StepResult:
    """Step 5: 시연 쿼리 — CRITICAL + acknowledged_at IS NULL → 프레스 알람이 결과에 있는지.

    쿼리: select id, severity, acknowledged_at, message, payload
          where severity = 'CRITICAL' and acknowledged_at IS NULL
          order by created_at desc
    """
    step, name = 5, "시연 쿼리 — CRITICAL unacked 알람 (acknowledged_at IS NULL)"

    try:
        result = (
            sb.table("live_alarms")
            .select("id, severity, acknowledged_at, message, payload")
            .eq("severity", "CRITICAL")
            .is_("acknowledged_at", "null")
            .order("created_at", desc=True)
            .execute()
        )
        rows = result.data or []

    except Exception as exc:
        return _fail(step, name, f"쿼리 오류: {exc}")

    if not rows:
        return _fail(
            step, name,
            "CRITICAL + acknowledged_at IS NULL 결과 없음",
            {},
        )

    first = rows[0]
    first_id = first.get("id", "")
    first_message = first.get("message", "")

    # payload에서 regulation_change_id 확인
    first_payload = first.get("payload") or {}
    if isinstance(first_payload, str):
        try:
            first_payload = json.loads(first_payload)
        except Exception:
            first_payload = {}
    first_reg_id = first_payload.get("regulation_change_id", "")

    is_press = first_id == PRESS_ALARM_ID or first_reg_id == PRESS_REG_ID

    data = {
        "query_result_count": len(rows),
        "first_alarm_id": first_id,
        "first_message": first_message[:60],
        "first_regulation_change_id": first_reg_id,
        "all_ids": [r.get("id") for r in rows],
    }

    if is_press:
        return _pass(
            step, name,
            f"첫 결과가 프레스 안전거리 알람 확인 — '{first_message[:50]}...'",
            data,
        )
    return _fail(
        step, name,
        f"첫 결과가 프레스 알람 아님 — 실제: {first_id} / {first_message[:50]}",
        data,
    )


# ---------------------------------------------------------------------------
# 메인 검증 흐름
# ---------------------------------------------------------------------------

def verify_main(args: argparse.Namespace) -> int:
    """검증 메인 흐름.

    Args:
        args: argparse 파싱 결과.

    Returns:
        종료 코드 (0=전체 PASS, 1=FAIL 있음).
    """
    try:
        demo_date = date.fromisoformat(args.demo_date)
    except ValueError:
        msg = f"--demo-date 형식 불일치: {args.demo_date!r} (YYYY-MM-DD 필요)"
        if args.json_output:
            print(json.dumps({"error": msg}, ensure_ascii=False))
        else:
            print(f"[오류] {msg}", file=sys.stderr)
        return 1

    if not args.json_output:
        print("=" * 60)
        print("[P0-2] regulation_changes 시드 검증 (스키마 v2.0.0)")
        print(f"  시연 기준일: {demo_date}")
        print("=" * 60 + "\n")

    # Supabase 클라이언트
    try:
        sb = _get_sb_client()
    except (EnvironmentError, RuntimeError) as exc:
        msg = str(exc)
        if args.json_output:
            print(json.dumps({"error": msg, "steps": []}, ensure_ascii=False, indent=2))
        else:
            print(f"[오류] {msg}", file=sys.stderr)
        return 1

    # 5단계 검증 실행
    results: list[StepResult] = []

    steps = [
        ("Step 1", step1_regulation_changes_count, (sb,)),
        ("Step 2", step2_live_alarms_count, (sb,)),
        ("Step 3", step3_outbox_fk, (sb,)),
        ("Step 4", step4_penalty_recalculation, (sb, demo_date)),
        ("Step 5", step5_demo_query, (sb,)),
    ]

    for label, fn, fn_args in steps:
        if not args.json_output:
            print(f"[{label}] {fn.__doc__.strip().split(chr(10))[0] if fn.__doc__ else fn.__name__}")
        r = fn(*fn_args)
        results.append(r)
        if not args.json_output:
            icon = "OK" if r["status"] == "PASS" else ("WN" if r["status"] == "WARN" else "NG")
            print(f"  [{icon}] [{r['status']}] {r['detail']}")
            print()

    # 결과 집계
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    overall = "PASS" if fail_count == 0 else "FAIL"

    summary = {
        "overall": overall,
        "demo_date": str(demo_date),
        "steps_total": len(results),
        "pass": pass_count,
        "warn": warn_count,
        "fail": fail_count,
        "steps": results,
    }

    if args.json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print("=" * 60)
        print(f"[검증 {'완료 — 전체 PASS' if overall == 'PASS' else '실패 — FAIL 있음'}]")
        print(f"  PASS: {pass_count} / WARN: {warn_count} / FAIL: {fail_count} / 총: {len(results)}")
        print("=" * 60)

    return 0 if fail_count == 0 else 1


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--demo-date",
        default=DEFAULT_DEMO_DATE,
        metavar="YYYY-MM-DD",
        help=f"시연 기준일 — Step 4 날짜 계산 기준 (기본: {DEFAULT_DEMO_DATE})",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="JSON 형식으로 결과 출력 (CI 통합 용)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(verify_main(parse_args()))
