"""inspection_logs 시드 — Feature F Mock 제거 작업 후속.

생성: 6 checklist_templates × ~10일 = 약 50건 시연용 점검 이력.
멱등성: --reset 옵션으로 기존 row 삭제 후 재시드. 미지정 시 추가.

실행:
    python3 scripts/seed_inspection_logs.py             # 추가 시드
    python3 scripts/seed_inspection_logs.py --reset     # 초기화 후 시드
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from core.data_lineage import ensure_lineage_columns, lineage_values

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "equipment" / "inspection.db"

# (equipment_id, equipment_name) 후보 — 사양 27부서 × 6사업장 조직과 정합.
EQUIPMENT_FLEET = {
    "프레스": [
        ("PR-101", "프레스 #1 (경산 본사)"),
        ("PR-102", "프레스 #2 (경산 본사)"),
        ("PR-201", "프레스 #3 (경산 2공장)"),
        ("PR-301", "프레스 #4 (경주 구어)"),
    ],
    "용접기": [
        ("WD-101", "용접 #1 (경산 본사)"),
        ("WD-102", "용접 #2 (경산 본사)"),
        ("WD-201", "용접 #3 (경산 2공장)"),
    ],
    "로봇": [
        ("RB-101", "도장 로봇 #1 (경산 본사)"),
        ("RB-102", "검사 로봇 #2 (경산 2공장)"),
    ],
}

INSPECTORS = ["김민수", "박지훈", "이정연", "최유진", "정혜린", "한석민", "오현지"]

# overall_status 분포 — PASS 75%, WARN 18%, FAIL 7% (현실적 시연 비율)
STATUS_WEIGHTS = [("PASS", 0.75), ("WARN", 0.18), ("FAIL", 0.07)]


def _pick_status(rng: random.Random) -> str:
    r = rng.random()
    cum = 0.0
    for s, w in STATUS_WEIGHTS:
        cum += w
        if r < cum:
            return s
    return "PASS"


def _build_results(template_id: int, status: str, rng: random.Random) -> list[dict]:
    """체크리스트 항목 결과 — 사양에 따라 항목별 pass/fail/score."""
    n_items = rng.randint(4, 8)
    items = []
    for i in range(n_items):
        if status == "PASS":
            ok = True
        elif status == "WARN":
            ok = rng.random() > 0.25
        else:  # FAIL
            ok = rng.random() > 0.55
        items.append({
            "item_no": i + 1,
            "passed": ok,
            "score": rng.randint(75, 100) if ok else rng.randint(40, 70),
            "comment": "" if ok else rng.choice([
                "마모 한계 근접",
                "누유 흔적 발견",
                "이음 감지",
                "온도 상승",
                "캘리브레이션 편차",
            ]),
        })
    return items


def _generate_logs(conn: sqlite3.Connection, days: int, rng: random.Random) -> int:
    """checklist_templates 6개 × days 일자 만큼 점검 이력 생성."""
    ensure_lineage_columns(conn, "inspection_logs")
    try:
        conn.execute("ALTER TABLE inspection_logs ADD COLUMN source TEXT DEFAULT 'unknown'")
    except sqlite3.OperationalError:
        pass
    lineage = lineage_values("synthetic", "seed_equipment", "seed_equipment")
    templates = conn.execute(
        "SELECT id, equipment_type, checklist_type FROM checklist_templates"
    ).fetchall()
    if not templates:
        print("[error] checklist_templates 가 비어있습니다. 먼저 시드 필요.", file=sys.stderr)
        return 0

    today = date.today()
    inserted = 0
    rows = []
    for d_offset in range(days):
        insp_date = today - timedelta(days=d_offset)
        for tpl_id, eq_type, checklist_type in templates:
            # 일상점검은 매일, 주간은 주1회(월요일), 월간은 월1회(1일).
            if "일상" in checklist_type and insp_date.weekday() == 6:
                continue  # 일요일 휴무
            if "주간" in checklist_type and insp_date.weekday() != 0:
                continue
            if "월간" in checklist_type and insp_date.day != 1:
                continue

            fleet = EQUIPMENT_FLEET.get(eq_type, [("UNKNOWN", "미지정")])
            for eq_id, eq_name in fleet:
                status = _pick_status(rng)
                results = _build_results(tpl_id, status, rng)
                rows.append((
                    eq_id,
                    eq_name,
                    tpl_id,
                    rng.choice(INSPECTORS),
                    insp_date.isoformat(),
                    json.dumps(results, ensure_ascii=False),
                    status,
                    "" if status == "PASS" else f"{eq_type} {status} — 후속 조치 필요",
                    datetime.now().isoformat(timespec="seconds"),
                    "seed_equipment",
                    lineage["data_class"],
                    lineage["source_system"],
                    lineage["source_label"],
                    lineage["source_updated_at"],
                ))
                inserted += 1

    conn.executemany(
        """
        INSERT INTO inspection_logs
          (equipment_id, equipment_name, template_id, inspector,
           inspection_date, results_json, overall_status, note, created_at, source,
           data_class, source_system, source_label, source_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="inspection_logs 시드")
    parser.add_argument("--reset", action="store_true", help="기존 row 전부 삭제 후 시드")
    parser.add_argument("--days", type=int, default=30, help="과거 N일 (기본 30)")
    parser.add_argument("--seed", type=int, default=2026, help="난수 시드")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[error] DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    rng = random.Random(args.seed)
    with sqlite3.connect(DB_PATH) as conn:
        if args.reset:
            n_before = conn.execute("SELECT COUNT(*) FROM inspection_logs").fetchone()[0]
            conn.execute("DELETE FROM inspection_logs")
            print(f"[reset] inspection_logs {n_before} row 삭제")

        n_inserted = _generate_logs(conn, args.days, rng)
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM inspection_logs").fetchone()[0]
        print(f"[seed] {n_inserted} row 추가 / 총 {total} row")
        # 상태 분포 출력
        for status in ("PASS", "WARN", "FAIL"):
            cnt = conn.execute(
                "SELECT COUNT(*) FROM inspection_logs WHERE overall_status=?",
                (status,),
            ).fetchone()[0]
            print(f"  - {status}: {cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
