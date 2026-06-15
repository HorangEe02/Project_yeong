"""D 컴플라이언스 알람 시연용 시드 (v4.2 Phase 1).

다양한 severity·source 조합을 채워 대시보드 알람 카드 시연이 가능하도록 함.
멱등 — --reset 으로 이전 시드를 삭제 후 재시드.

실행:
    python3 scripts/seed_demo_compliance_alarm.py
    python3 scripts/seed_demo_compliance_alarm.py --reset
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "compliance_changes.db"

# (regulation_type, change_type, item_id, item_title, new_value, grade, summary_ko, days_until_effective, status, detected_days_ago)
# - days_until_effective: None=시행일 없음, 정수=오늘 + N일
# - status: 'pending'(기본) 또는 'action_required'(소스 4)
# - detected_days_ago: 0=오늘, N=과거 N일 전 (소스 4 7일+ 트리거용)
DEMO_ROWS = [
    # ─ 소스 1+3 (law_change + dday) ──────────────────────────────────
    (
        "산안법", "new", "OSH-2026-014",
        "산업안전보건법 시행규칙 일부개정 (프레스 안전거리)",
        "프레스 안전거리 기존 300mm → 400mm 확대. 시행 {date}. 본사·천안1·천안2 영향.",
        "CRITICAL",
        "프레스 안전거리 300→400mm 확대 — 본사 외 2개 사업장 검토 필요",
        25, "pending", 0,  # D-25 → law_change CRITICAL + dday HIGH
    ),
    (
        "관세법", "modified", "CUS-2026-007",
        "관세법 시행령 — HS코드 8708 부품 관세 5% 인하",
        "차체 부품 (HS 8708.29) 관세율 8% → 5%. 시행 {date}.",
        "HIGH",
        "현대·기아 협력 부품 수입 관세 3%p 인하 — 연간 비용 ~12억 절감 예상",
        5, "pending", 0,  # D-5 → law_change HIGH + dday CRITICAL
    ),
    (
        "MSDS", "added", "MSDS-2026-031",
        "MSDS 신규 등록 — 도장 용제 (자일렌 함유)",
        "도장 라인 신규 용제. 화학물질명: 자일렌(Xylene). 등록일 {date}.",
        "MEDIUM",
        "도장 신규 용제 — 노출허용기준 100ppm. 환기·PPE 보강 필요",
        None, "pending", 0,  # 시행일 없음 → law_change HIGH만
    ),
    (
        "EU CBAM", "modified", "CBAM-2026-002",
        "EU CBAM 전환기간 종료 — 본격 과세 시작",
        "CBAM 본격 과세 {date} 시행. 철강·알루미늄 부품 영향.",
        "HIGH",
        "EU 수출 부품 CBAM 인증서 의무 — 베트남 법인 우선 영향",
        12, "pending", 0,  # D-12 → law_change HIGH + dday HIGH
    ),
    (
        "ISO", "modified", "ISO-2026-001",
        "ISO 14001:2025 개정 (환경경영시스템)",
        "ISO 14001 일부 조항 개정. 전환 기간 36개월.",
        "MEDIUM",
        "기존 14001:2015 인증 유효. 전환 일정 수립 필요",
        None, "pending", 0,
    ),
    # ─ 소스 4 (unresolved 7일+) ─────────────────────────────────────
    (
        "산안법", "modified", "OSH-2026-008",
        "산안법 시행규칙 — 정기 안전점검 주기 단축",
        "정기 안전점검 6개월 → 3개월 주기 변경.",
        "HIGH",
        "안전보건팀 후속 조치 필요 — 점검 일정 재편 미완",
        None, "action_required", 12,  # 12일 전 발견, 미해결 → unresolved HIGH
    ),
    (
        "관세법", "modified", "CUS-2026-004",
        "관세법 시행령 — 자유무역지역 신고 절차 강화",
        "베트남 법인 부품 반입 절차 변경 — 사전 신고 의무.",
        "CRITICAL",
        "구매·물류팀 협업 필요 — 베트남 법인 절차 재정의 미완",
        None, "action_required", 20,  # 20일 전 → unresolved CRITICAL
    ),
    # ─ 소스 5 (trend spike) — 최근 1일에 7건 집중 ─────────────────────
    *[
        (
            f"AdHoc-Spike{i}", "new", f"SPK-2026-{i:03d}",
            f"신규 규제 spike #{i}",
            f"트렌드 spike 시연용 신규 규제 #{i}.",
            "LOW",
            "트렌드 급증 시뮬레이션 — 평소 1-2건/일 대비 7건/일",
            None, "pending", 0,
        )
        for i in range(1, 8)  # 7개 — 평소 평균(1-2) + 2σ 초과 유발
    ],
]


def _format_new_value(template: str, days_until: int | None) -> str:
    if days_until is None:
        return template.replace(" 시행 {date}.", "")
    eff = date.today() + timedelta(days=days_until)
    return template.format(date=eff.isoformat())


def _seed(conn: sqlite3.Connection, reset: bool) -> int:
    if reset:
        item_ids = tuple(r[2] for r in DEMO_ROWS)
        placeholders = ",".join("?" for _ in item_ids)
        n = conn.execute(
            f"SELECT COUNT(*) FROM regulation_changes WHERE item_id IN ({placeholders})",
            item_ids,
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM regulation_changes WHERE item_id IN ({placeholders})",
            item_ids,
        )
        # ack 테이블도 D-*-<rowid> 키로 잔존할 수 있으므로 정리 시도 (alarm_aggregator 가 알아서 무시).
        print(f"[reset] 시드용 row {n}건 삭제 ({len(item_ids)} item_id)")

    inserted = 0
    now = datetime.now()
    for row in DEMO_ROWS:
        reg_type, change_type, item_id, title, nv_tmpl, grade, summary, days, status, detected_days_ago = row
        # 중복 체크 — 동일 item_id 가 이미 있으면 skip
        existing = conn.execute(
            "SELECT id FROM regulation_changes WHERE item_id = ?", (item_id,)
        ).fetchone()
        if existing:
            print(f"  skip {item_id} (이미 존재, id={existing[0]})")
            continue

        detected_at = (now - timedelta(days=detected_days_ago)).isoformat(timespec="seconds")
        new_value = _format_new_value(nv_tmpl, days)
        conn.execute(
            """
            INSERT INTO regulation_changes
              (detected_at, regulation_type, change_type, item_id, item_title,
               old_value, new_value, severity, acknowledged,
               status, summary_ko, grade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                detected_at, reg_type, change_type, item_id, title,
                "", new_value,
                "warning" if grade in ("CRITICAL", "HIGH") else "info",
                status, summary, grade,
            ),
        )
        inserted += 1
        dday_str = f"D-{days}" if days else "N/A"
        age_str = f"{detected_days_ago}일전" if detected_days_ago else "오늘"
        print(f"  + {reg_type:10s} {change_type:8s} {item_id} grade={grade} {dday_str} status={status} ({age_str})")
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="D 컴플라이언스 알람 시연용 시드")
    parser.add_argument("--reset", action="store_true", help="기존 시드 row 삭제 후 재시드")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[error] DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    with sqlite3.connect(DB_PATH) as conn:
        inserted = _seed(conn, args.reset)
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM regulation_changes").fetchone()[0]
        unack = conn.execute(
            "SELECT COUNT(*) FROM regulation_changes WHERE acknowledged=0"
        ).fetchone()[0]
        print(f"[seed] {inserted}건 추가 / 전체 {total}건 / 미ack {unack}건")
        print("→ Phase 1.4 확인: python3 scripts/diagnose_compliance_alarms.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
