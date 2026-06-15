#!/usr/bin/env python3
"""아진산업 AJIN Supabase regulation_changes + live_alarms + notification_outbox 시드 스크립트.

P0-2 법규 모니터링 시연 시드 — 시나리오 3건 + 알림 3건 + 발송함 4건.
실제 Supabase 스키마 기준 (v2.0.0): 시나리오 디테일은 payload JSON에 저장.

기본은 --dry-run (JSON 로드 + penalty 재계산만, DB 업서트 없음).
--apply 플래그로 실제 Supabase 업서트를 실행한다.

사용 예:
    python3 scripts/seed_supabase_regulations.py
    python3 scripts/seed_supabase_regulations.py --dry-run
    python3 scripts/seed_supabase_regulations.py --apply
    python3 scripts/seed_supabase_regulations.py --apply --demo-date=2026-06-10
    python3 scripts/seed_supabase_regulations.py --apply --source=data/demo_scenarios/regulation_seed.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 경로 설정 — penalty_calculator import
# ---------------------------------------------------------------------------

# 스크립트: ajin-ai-assistant-react/scripts/seed_supabase_regulations.py
# ROOT  : 04_AJIN/
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent          # ajin-ai-assistant-react/
ROOT = REPO_ROOT.parent                 # 04_AJIN/

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
PROGRESS_FILE = Path("/tmp/seed_regulations_progress.json")

DEFAULT_SOURCE = "data/demo_scenarios/regulation_seed.json"
DEFAULT_DEMO_DATE = "2026-06-10"


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def _mask_secret(value: str) -> str:
    """시크릿 값 마스킹 (앞 8자 + ***)."""
    if not value:
        return "***"
    return value[:8] + "***"


def _load_progress() -> dict[str, Any]:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_progress(progress: dict[str, Any]) -> None:
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _iso_kst(dt: datetime) -> str:
    """datetime → ISO 8601 with +09:00."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 데이터 타입
# ---------------------------------------------------------------------------

Scenario = dict[str, Any]
Alarm = dict[str, Any]
Outbox = dict[str, Any]


# ---------------------------------------------------------------------------
# Step 1: 시드 JSON 로딩
# ---------------------------------------------------------------------------

def load_scenarios(source_path: str | Path) -> tuple[list[Scenario], list[Alarm], list[Outbox]]:
    """regulation_seed.json을 읽어 (scenarios, alarms, outbox) 반환.

    Args:
        source_path: JSON 경로 (절대 또는 repo 루트 기준 상대).

    Returns:
        (regulation_changes 리스트, live_alarms 리스트, notification_outbox 리스트)
    """
    path = Path(source_path)
    if not path.is_absolute():
        path = REPO_ROOT / path

    if not path.exists():
        raise FileNotFoundError(f"시드 파일 없음: {path}")

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    scenarios: list[Scenario] = raw.get("regulation_changes", [])
    alarms: list[Alarm] = raw.get("live_alarms", [])
    outbox: list[Outbox] = raw.get("notification_outbox", [])

    if not scenarios:
        raise ValueError("regulation_changes 배열이 비어 있습니다.")

    return deepcopy(scenarios), deepcopy(alarms), deepcopy(outbox)


# ---------------------------------------------------------------------------
# Step 2: penalty 재계산
# ---------------------------------------------------------------------------

def recalculate_penalty(scenario: Scenario, demo_date: date) -> Scenario:
    """scenario payload의 penalty_severity_krw_mn을 penalty_calculator로 재계산.

    penalty_calculator를 import할 수 없으면 payload 원래 값을 유지한다.
    결과는 payload JSON 내부에 저장 (top-level 컬럼 없음).

    Args:
        scenario: regulation_changes 단일 row dict (payload 포함).
        demo_date: 시연 기준일 (days_to_effective 계산 기준).

    Returns:
        payload 내 penalty 필드가 갱신된 scenario (in-place + return).
    """
    if not _PENALTY_AVAILABLE:
        print(
            f"  [경고] penalty_calculator import 실패 — 원래 값 유지: {_PENALTY_IMPORT_ERROR}",
            file=sys.stderr,
        )
        return scenario

    payload = scenario.get("payload", {})
    effective_str = payload.get("effective_date", "")
    try:
        effective = date.fromisoformat(effective_str)
    except (ValueError, TypeError):
        print(f"  [경고] payload.effective_date 파싱 실패: {effective_str!r} — penalty 재계산 스킵")
        return scenario

    days_to_effective = (effective - demo_date).days
    grade = payload.get("grade", "MEDIUM")
    legal_class = payload.get("legal_class", "_default")

    # 설비 수: payload.facility_count 우선, affected_facilities 리스트 길이 fallback
    n_facilities = payload.get("facility_count") or len(payload.get("affected_facilities", [1]))
    n_facilities = max(int(n_facilities), 1)

    result = calculate_noncompliance_penalty(
        grade=grade,
        affected_facilities=n_facilities,
        days_to_effective=days_to_effective,
        law_category=legal_class,
    )

    # payload 내부에 저장 (top-level 컬럼 없음)
    payload["penalty_severity_krw_mn"] = result.estimated_fine_krw_mn
    payload["penalty_risk_score"] = result.risk_score
    payload["penalty_explanation"] = result.explanation
    scenario["payload"] = payload

    return scenario


# ---------------------------------------------------------------------------
# Step 3: detected_at / available_at 동적 조정
# ---------------------------------------------------------------------------

def adjust_demo_dates(
    scenarios: list[Scenario],
    alarms: list[Alarm],
    outbox: list[Outbox],
    demo_date: date,
) -> tuple[list[Scenario], list[Alarm], list[Outbox]]:
    """payload.audit_trail[0].ts·acknowledged_at·available_at을 시연 기준일 기준으로 동적 조정.

    시연 기준일(demo_date) 기준:
      - 시나리오 #1 (CRITICAL) : 어제 (demo_date - 1일)
      - 시나리오 #2 (HIGH)     : 그제 (demo_date - 2일)
      - 시나리오 #3 (MEDIUM)   : 3일 전 (demo_date - 3일)

    regulation_changes.created_at / live_alarms.created_at 은 Supabase default (CURRENT_TIMESTAMP).
    여기서는 payload 내 audit_trail[0].ts 와 acknowledged_at, available_at 만 조정한다.

    Args:
        scenarios: regulation_changes 리스트.
        alarms: live_alarms 리스트.
        outbox: notification_outbox 리스트.
        demo_date: 시연 기준일.

    Returns:
        날짜 조정된 (scenarios, alarms, outbox).
    """
    # 시나리오별 날짜 오프셋 (idx 순서로 적용)
    offsets_days = [1, 2, 3]
    # 시나리오별 감지 시각 (hour, minute) — 새벽 크롤링 시간대
    detect_times = [(2, 35), (3, 0), (2, 50)]

    # 시나리오 payload.audit_trail[0].ts 조정
    for i, s in enumerate(scenarios):
        offset = offsets_days[i] if i < len(offsets_days) else (i + 1)
        hour, minute = detect_times[i] if i < len(detect_times) else (3, i * 5)
        detected = datetime(
            *(demo_date - timedelta(days=offset)).timetuple()[:3],
            hour, minute, 0, tzinfo=KST
        )
        detected_iso = _iso_kst(detected)
        payload = s.get("payload", {})
        audit = payload.get("audit_trail", [])
        if audit:
            audit[0]["ts"] = detected_iso
        payload["audit_trail"] = audit
        s["payload"] = payload

    # live_alarms acknowledged_at 조정 (null 유지는 그대로, 승인된 건만 갱신)
    # idx 2 (MEDIUM) 는 acknowledged_at 있음 → 3일전 14:00으로 조정
    alarm_ack_schedule = [None, None, (3, 14, 0)]
    for i, a in enumerate(alarms):
        if i < len(alarm_ack_schedule) and alarm_ack_schedule[i] is not None:
            d_offset, hour, minute = alarm_ack_schedule[i]
            ack_dt = datetime(
                *(demo_date - timedelta(days=d_offset)).timetuple()[:3],
                hour, minute, 0, tzinfo=KST
            )
            a["acknowledged_at"] = _iso_kst(ack_dt)
        else:
            a["acknowledged_at"] = None

    # outbox available_at 조정 (null 유지는 그대로)
    # outbox 배열: idx 0 미발송, idx 1 그제 09:00, idx 2 그제 09:01, idx 3 3일전 10:30
    outbox_schedule = [
        None,
        (2, 9, 0),     # 그제 09:00
        (2, 9, 1),     # 그제 09:01
        (3, 10, 30),   # 3일전 10:30
    ]
    for i, ob in enumerate(outbox):
        if i < len(outbox_schedule) and outbox_schedule[i] is not None:
            d_offset, hour, minute = outbox_schedule[i]
            avail_dt = datetime(
                *(demo_date - timedelta(days=d_offset)).timetuple()[:3],
                hour, minute, 0, tzinfo=KST
            )
            ob["available_at"] = _iso_kst(avail_dt)
        else:
            ob["available_at"] = None

    return scenarios, alarms, outbox


# ---------------------------------------------------------------------------
# Step 4: Supabase 업서트 — 실제 스키마 컬럼 매핑
# ---------------------------------------------------------------------------

def _build_regulation_row(s: Scenario) -> dict[str, Any]:
    """regulation_changes 테이블 실제 컬럼 매핑.

    실제 컬럼: id, source, title, severity, status, url, payload,
               data_class, source_system, source_label
    시나리오 디테일(regulation_name, article, before_text 등)은 payload에 저장.
    """
    return {
        "id": s["id"],
        "source": s.get("source", "unknown"),
        "title": s.get("title", ""),
        "severity": s.get("severity", "MEDIUM"),
        "status": s.get("status", "new"),
        "url": s.get("url", ""),
        "payload": s.get("payload", {}),
        "data_class": s.get("data_class", "demo"),
        "source_system": s.get("source_system", "unknown"),
        "source_label": s.get("source_label", ""),
    }


def _build_alarm_row(a: Alarm) -> dict[str, Any]:
    """live_alarms 테이블 실제 컬럼 매핑.

    실제 컬럼: id, domain, severity, message, acknowledged_at, payload,
               data_class, source_system
    acknowledged_at: NULL=미승인, timestamptz=승인됨
    """
    return {
        "id": a["id"],
        "domain": a.get("domain", "equipment"),
        "severity": a.get("severity", "info"),
        "message": a.get("message", ""),
        "acknowledged_at": a.get("acknowledged_at"),  # None → NULL (미승인)
        "payload": a.get("payload", {}),
        "data_class": a.get("data_class", "demo"),
        "source_system": a.get("source_system", "unknown"),
    }


def _build_outbox_row(ob: Outbox) -> dict[str, Any]:
    """notification_outbox 테이블 실제 컬럼 매핑.

    실제 컬럼: id, event_type, target, status, payload, available_at,
               data_class
    """
    return {
        "id": ob["id"],
        "event_type": ob.get("event_type", "regulation_change"),
        "target": ob.get("target", ""),
        "status": ob.get("status", "queued"),
        "payload": ob.get("payload", {}),
        "available_at": ob.get("available_at"),  # None → NULL
        "data_class": ob.get("data_class", "demo"),
    }


def upsert_regulations(sb: Any, scenarios: list[Scenario]) -> list[str]:
    """regulation_changes 테이블에 시나리오 업서트.

    Args:
        sb: supabase-py 클라이언트.
        scenarios: regulation_changes 행 리스트.

    Returns:
        업서트된 regulation id 리스트.
    """
    reg_ids: list[str] = []
    for s in scenarios:
        row = _build_regulation_row(s)
        try:
            result = (
                sb.table("regulation_changes")
                .upsert(row, on_conflict="id")
                .execute()
            )
        except Exception as exc:
            err_str = str(exc)
            if "PGRST204" in err_str:
                raise RuntimeError(
                    f"PGRST204 컬럼 미스매치 — regulation_changes 업서트 실패.\n"
                    f"  row keys: {list(row.keys())}\n"
                    f"  원인: {exc}"
                ) from exc
            if "42501" in err_str:
                raise RuntimeError(
                    f"권한 오류 (42501) — SUPABASE_SECRET_KEY 확인 필요.\n"
                    f"  set -a; source .env; set +a 후 재실행\n원인: {exc}"
                ) from exc
            raise
        if result.data:
            for row_r in result.data:
                reg_ids.append(row_r.get("id", s["id"]))
        else:
            reg_ids.append(s["id"])
    return reg_ids


def upsert_alarms(sb: Any, alarms: list[Alarm]) -> None:
    """live_alarms 테이블에 알람 업서트.

    Args:
        sb: supabase-py 클라이언트.
        alarms: live_alarms 행 리스트.
    """
    for a in alarms:
        row = _build_alarm_row(a)
        try:
            sb.table("live_alarms").upsert(row, on_conflict="id").execute()
        except Exception as exc:
            err_str = str(exc)
            if "PGRST204" in err_str:
                raise RuntimeError(
                    f"PGRST204 컬럼 미스매치 — live_alarms 업서트 실패.\n"
                    f"  row keys: {list(row.keys())}\n원인: {exc}"
                ) from exc
            if "42501" in err_str:
                raise RuntimeError(
                    f"권한 오류 (42501) — SUPABASE_SECRET_KEY 확인 필요.\n"
                    f"  set -a; source .env; set +a 후 재실행\n원인: {exc}"
                ) from exc
            raise


def upsert_outbox(sb: Any, outbox: list[Outbox]) -> None:
    """notification_outbox 테이블에 발송함 업서트.

    FK 순서: regulation_changes → live_alarms → notification_outbox.
    이 함수는 regulation_changes, live_alarms 업서트 후에 호출해야 한다.

    Args:
        sb: supabase-py 클라이언트.
        outbox: notification_outbox 행 리스트.
    """
    for ob in outbox:
        row = _build_outbox_row(ob)
        try:
            sb.table("notification_outbox").upsert(row, on_conflict="id").execute()
        except Exception as exc:
            err_str = str(exc)
            if "PGRST204" in err_str:
                raise RuntimeError(
                    f"PGRST204 컬럼 미스매치 — notification_outbox 업서트 실패.\n"
                    f"  row keys: {list(row.keys())}\n원인: {exc}"
                ) from exc
            if "42501" in err_str:
                raise RuntimeError(
                    f"권한 오류 (42501) — SUPABASE_SECRET_KEY 확인 필요.\n"
                    f"  set -a; source .env; set +a 후 재실행\n원인: {exc}"
                ) from exc
            raise


# ---------------------------------------------------------------------------
# 메인 시드 흐름
# ---------------------------------------------------------------------------

def seed_main(args: argparse.Namespace) -> int:
    """시드 메인 흐름.

    Args:
        args: argparse 파싱 결과.

    Returns:
        종료 코드 (0=성공, 1=오류, 2=환경변수 오류).
    """
    # tqdm 선택적 import (없으면 passthrough)
    try:
        from tqdm import tqdm
    except ImportError:
        class tqdm:  # type: ignore[no-redef]
            def __init__(self, iterable=None, **kwargs):
                self._it = iter(iterable) if iterable is not None else iter([])
                total = kwargs.get("total", "?")
                desc = kwargs.get("desc", "")
                print(f"[진행] {desc} (total={total})")

            def __iter__(self):
                return self

            def __next__(self):
                return next(self._it)

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def set_postfix_str(self, s: str):
                print(f"  {s}")

    # ── 시연 기준일 파싱 ──
    try:
        demo_date = date.fromisoformat(args.demo_date)
    except ValueError:
        print(f"[오류] --demo-date 형식 불일치: {args.demo_date!r} (YYYY-MM-DD 필요)", file=sys.stderr)
        return 1

    print("=" * 60)
    print("[P0-2] regulation_changes 시드 스크립트 (스키마 v2.0.0)")
    print(f"  모드       : {'--apply (실제 DB 업서트)' if args.apply else '--dry-run (JSON + penalty 재계산만)'}")
    print(f"  시연 기준일: {demo_date}")
    print(f"  소스 파일  : {args.source}")
    print("=" * 60)

    # ── [1/5] JSON 로딩 ──
    print("\n[1/5] 시드 JSON 로딩")
    try:
        scenarios, alarms, outbox = load_scenarios(args.source)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    print(f"  regulation_changes : {len(scenarios)}건")
    print(f"  live_alarms        : {len(alarms)}건")
    print(f"  notification_outbox: {len(outbox)}건")

    # ── [2/5] 날짜 동적 조정 ──
    print("\n[2/5] 시연 날짜 동적 조정 (demo_date 기준 어제·그제·3일전)")
    scenarios, alarms, outbox = adjust_demo_dates(scenarios, alarms, outbox, demo_date)
    for s in scenarios:
        audit_trail = s.get("payload", {}).get("audit_trail", [])
        first_ts = audit_trail[0]["ts"] if audit_trail else "N/A"
        print(f"  {s['id']}: payload.audit_trail[0].ts={first_ts}")

    # ── [3/5] penalty 재계산 ──
    print("\n[3/5] penalty_calculator 재계산 (결과 → payload.penalty_severity_krw_mn)")
    if _PENALTY_AVAILABLE:
        for s in tqdm(scenarios, desc="penalty 재계산", total=len(scenarios)):
            recalculate_penalty(s, demo_date)
            p = s.get("payload", {})
            print(
                f"  {s['id']}: ₩{p.get('penalty_severity_krw_mn', 'N/A')}mn "
                f"(risk={p.get('penalty_risk_score', 'N/A')})"
            )
    else:
        print(f"  [경고] penalty_calculator 사용 불가 — 원래 값 유지. 오류: {_PENALTY_IMPORT_ERROR}")
        for s in scenarios:
            p = s.get("payload", {})
            print(
                f"  {s['id']}: ₩{p.get('penalty_severity_krw_mn', 'N/A')}mn (payload 원래 값)"
            )

    # ── dry-run 완료 ──
    if args.dry_run:
        print("\n" + "=" * 60)
        print("[dry-run 완료] --apply 없이 재계산만 수행했습니다.\n")
        _print_dry_run_summary(scenarios, alarms, outbox)
        return 0

    # ── [4/5] Supabase 클라이언트 초기화 ──
    print("\n[4/5] Supabase 클라이언트 초기화")

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")

    if not supabase_url or not supabase_key:
        print(
            "[오류] 환경변수 부재. 아래 명령 후 재실행:\n"
            "  set -a; source .env; set +a",
            file=sys.stderr,
        )
        return 2

    print(f"  URL : {supabase_url}")
    print(f"  KEY : {_mask_secret(supabase_key)}")

    try:
        from supabase import create_client
    except ImportError:
        print("[오류] supabase 패키지가 필요합니다: pip install supabase", file=sys.stderr)
        return 1

    sb = create_client(supabase_url, supabase_key)
    print("  클라이언트 생성 완료")

    # ── [5/5] 업서트 (FK 순서: regulations → alarms → outbox) ──
    print("\n[5/5] Supabase 업서트 (FK 순서 보장)")
    progress = _load_progress()
    stats = {"reg_ok": 0, "alarm_ok": 0, "outbox_ok": 0, "failed": 0}
    errors: list[str] = []

    # 5-a: regulation_changes
    print("\n  [5-a] regulation_changes 업서트")
    try:
        for s in tqdm(scenarios, desc="regulation_changes", total=len(scenarios)):
            try:
                upsert_regulations(sb, [s])
                stats["reg_ok"] += 1
                progress[s["id"]] = "done"
                _save_progress(progress)
                print(f"    OK {s['id']}")
            except Exception as exc:
                msg = f"regulation {s['id']}: {exc}"
                print(f"    NG {msg}", file=sys.stderr)
                stats["failed"] += 1
                errors.append(msg)
                progress[s["id"]] = f"failed: {exc}"
                _save_progress(progress)
    except Exception as exc:
        print(f"  [오류] regulation_changes 업서트 실패: {exc}", file=sys.stderr)
        return 1

    # 5-b: live_alarms
    print("\n  [5-b] live_alarms 업서트")
    try:
        for a in tqdm(alarms, desc="live_alarms", total=len(alarms)):
            try:
                upsert_alarms(sb, [a])
                stats["alarm_ok"] += 1
                progress[a["id"]] = "done"
                _save_progress(progress)
                print(f"    OK {a['id']}")
            except Exception as exc:
                msg = f"alarm {a['id']}: {exc}"
                print(f"    NG {msg}", file=sys.stderr)
                stats["failed"] += 1
                errors.append(msg)
    except Exception as exc:
        print(f"  [오류] live_alarms 업서트 실패: {exc}", file=sys.stderr)
        return 1

    # 5-c: notification_outbox
    print("\n  [5-c] notification_outbox 업서트")
    try:
        for ob in tqdm(outbox, desc="notification_outbox", total=len(outbox)):
            try:
                upsert_outbox(sb, [ob])
                stats["outbox_ok"] += 1
                progress[ob["id"]] = "done"
                _save_progress(progress)
                print(f"    OK {ob['id']}")
            except Exception as exc:
                msg = f"outbox {ob['id']}: {exc}"
                print(f"    NG {msg}", file=sys.stderr)
                stats["failed"] += 1
                errors.append(msg)
    except Exception as exc:
        print(f"  [오류] notification_outbox 업서트 실패: {exc}", file=sys.stderr)
        return 1

    # ── 최종 결과 ──
    print("\n" + "=" * 60)
    print("[시드 완료]")
    print(f"  regulation_changes 업서트: {stats['reg_ok']}건")
    print(f"  live_alarms 업서트       : {stats['alarm_ok']}건")
    print(f"  notification_outbox 업서트: {stats['outbox_ok']}건")
    print(f"  실패                     : {stats['failed']}건")
    if errors:
        print("\n  실패 목록:")
        for e in errors:
            print(f"    - {e}")
    print(f"\n  진행 기록: {PROGRESS_FILE}")
    print("=" * 60)

    return 1 if stats["failed"] > 0 else 0


def _print_dry_run_summary(
    scenarios: list[Scenario],
    alarms: list[Alarm],
    outbox: list[Outbox],
) -> None:
    """dry-run 결과 요약 출력."""
    print("  === regulation_changes (실제 업서트 컬럼) ===")
    print(f"  {'ID':<40} {'severity':<10} {'status':<10} {'penalty (mn)':>12} {'risk':>8}")
    print(f"  {'-'*85}")
    for s in scenarios:
        p = s.get("payload", {})
        print(
            f"  {s['id']:<40} {s.get('severity', 'N/A'):<10} {s.get('status', 'N/A'):<10} "
            f"{p.get('penalty_severity_krw_mn', 'N/A'):>12} "
            f"{p.get('penalty_risk_score', 'N/A'):>8}"
        )
    print("\n  컬럼 매핑: id, source, title, severity, status, url, payload, data_class, source_system, source_label")

    print(f"\n  === live_alarms (실제 업서트 컬럼) ===")
    print(f"  {'ID':<30} {'severity':<10} {'acknowledged_at':<30}")
    print(f"  {'-'*75}")
    for a in alarms:
        ack = a.get("acknowledged_at") or "NULL (미승인)"
        print(f"  {a['id']:<30} {a.get('severity', 'N/A'):<10} {ack:<30}")
    print("\n  컬럼 매핑: id, domain, severity, message, acknowledged_at, payload, data_class, source_system")

    print(f"\n  === notification_outbox (실제 업서트 컬럼) ===")
    print(f"  {'ID':<35} {'target':<15} {'status':<10} {'available_at'}")
    print(f"  {'-'*80}")
    for ob in outbox:
        avail = ob.get("available_at") or "NULL (미발송)"
        print(f"  {ob['id']:<35} {ob.get('target', 'N/A'):<15} {ob.get('status', 'N/A'):<10} {avail}")
    print("\n  컬럼 매핑: id, event_type, target, status, payload, available_at, data_class")

    total = len(scenarios) + len(alarms) + len(outbox)
    print(f"\n  총 행 수: {total} (regulations={len(scenarios)}, alarms={len(alarms)}, outbox={len(outbox)})")


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="JSON 로드 + penalty 재계산만, DB 업서트 없음 (기본값)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="실제 Supabase 업서트 실행",
    )

    parser.add_argument(
        "--demo-date",
        default=DEFAULT_DEMO_DATE,
        metavar="YYYY-MM-DD",
        help=f"시연 기준일 — payload.audit_trail[0].ts / acknowledged_at / available_at 동적 계산 기준 (기본: {DEFAULT_DEMO_DATE})",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"시드 JSON 경로 (repo 루트 기준, 기본: {DEFAULT_SOURCE})",
    )

    args = parser.parse_args()

    # --apply 지정 시 dry_run=False
    if args.apply:
        args.dry_run = False

    return args


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(seed_main(parse_args()))
