"""inspection_logs 합성 → 운영 마이그레이션 (v4.3 Phase 4).

수행 단계:
1. DB 자동 백업: inspection.db → inspection.db.<ts>.bak
2. source 컬럼 멱등 추가 (ensure_etl_tables 가 처리)
3. seed_inspection_logs.py 가 만든 row 식별 후 source='synthetic' 마킹
4. 합성 row 삭제 (--apply 플래그 필요)
5. 자연키 unique index 생성

식별 기준 (seed_inspection_logs.INSPECTORS + EQUIPMENT_FLEET 매칭):
- inspector ∈ 7명 합성 명단
- equipment_id 가 PR/WD/RB prefix (시드 fleet)
- source 이미 'synthetic' 아닐 때만 마킹

실행:
    python3 scripts/migrate_inspection_drop_synthetic.py            # 보고서만 (dry)
    python3 scripts/migrate_inspection_drop_synthetic.py --apply    # 실제 삭제
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "equipment" / "inspection.db"

# scripts/seed_inspection_logs.py 의 합성 데이터 식별 단서
SYNTHETIC_INSPECTORS = {"김민수", "박지훈", "이정연", "최유진", "정혜린", "한석민", "오현지"}
SYNTHETIC_EQUIPMENT_PREFIXES = ("PR-", "WD-", "RB-")


def _backup(db_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = db_path.with_name(f"{db_path.name}.{ts}.bak")
    shutil.copy2(db_path, bak)
    return bak


def _ensure_source_column(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE inspection_logs ADD COLUMN source TEXT DEFAULT 'unknown'")
    except sqlite3.OperationalError:
        pass


def _mark_synthetic(conn: sqlite3.Connection) -> int:
    placeholders = ",".join("?" for _ in SYNTHETIC_INSPECTORS)
    prefixes_clause = " OR ".join("equipment_id LIKE ?" for _ in SYNTHETIC_EQUIPMENT_PREFIXES)
    sql = f"""
        UPDATE inspection_logs
        SET source = 'synthetic'
        WHERE source != 'synthetic'
          AND inspector IN ({placeholders})
          AND ({prefixes_clause})
    """
    params = list(SYNTHETIC_INSPECTORS) + [f"{p}%" for p in SYNTHETIC_EQUIPMENT_PREFIXES]
    cur = conn.execute(sql, params)
    return cur.rowcount


def _delete_synthetic(conn: sqlite3.Connection) -> int:
    cur = conn.execute("DELETE FROM inspection_logs WHERE source = 'synthetic'")
    return cur.rowcount


def _try_create_unique_index(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_natural "
            "ON inspection_logs(equipment_id, template_id, inspection_date, inspector)"
        )
        return True
    except sqlite3.OperationalError as e:
        print(f"[warn] unique index 생성 실패 (자연키 중복 잔존?): {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="inspection_logs 합성 데이터 마이그레이션")
    parser.add_argument("--apply", action="store_true", help="실제 삭제 + 인덱스 생성")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[error] DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    if args.apply:
        bak = _backup(DB_PATH)
        print(f"[backup] {bak}")

    with sqlite3.connect(DB_PATH) as conn:
        _ensure_source_column(conn)
        marked = _mark_synthetic(conn)

        synthetic_count = conn.execute(
            "SELECT COUNT(*) FROM inspection_logs WHERE source='synthetic'"
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM inspection_logs").fetchone()[0]

        print(f"[mark] synthetic 마킹: {marked} 건")
        print(f"[count] 전체 {total} / synthetic {synthetic_count} / 운영 {total - synthetic_count}")

        if not args.apply:
            print("[dry-run] --apply 미지정 → 삭제·인덱스 생성 건너뜀")
            conn.rollback()  # source 마킹도 미반영
            return 0

        deleted = _delete_synthetic(conn)
        print(f"[delete] synthetic row 삭제: {deleted} 건")

        idx_ok = _try_create_unique_index(conn)
        if idx_ok:
            print("[index] uq_inspection_natural 생성 완료")

        conn.commit()
        remaining = conn.execute("SELECT COUNT(*) FROM inspection_logs").fetchone()[0]
        print(f"[done] 마이그레이션 완료. 잔여 {remaining} 건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
