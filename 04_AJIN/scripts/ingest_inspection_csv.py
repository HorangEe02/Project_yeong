"""점검 이력 CSV 적재 CLI — 운영팀 수동 백필용 (v4.3 Phase 1.7).

사용:
    python3 scripts/ingest_inspection_csv.py path/to/file.csv
    python3 scripts/ingest_inspection_csv.py path/to/file.csv --dry-run
    python3 scripts/ingest_inspection_csv.py path/to/file.csv --source manual_backfill --actor "안전보건팀"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from features.equipment.inspection_etl import ingest_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="inspection_logs CSV 적재")
    parser.add_argument("path", help="CSV 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="검증만 수행, DB 무변경")
    parser.add_argument("--source", default="csv_upload", help="source 라벨")
    parser.add_argument("--actor", default="cli", help="ingest_log.actor")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[error] 파일 없음: {path}", file=sys.stderr)
        return 1

    data = path.read_bytes()
    result = ingest_csv(
        data,
        source=args.source,
        actor=args.actor,
        file_name=path.name,
        dry_run=args.dry_run,
    )

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[{mode}] {path.name}")
    print(f"  total    {result.rows_total}")
    print(f"  inserted {result.rows_inserted}")
    print(f"  updated  {result.rows_updated}")
    print(f"  skipped  {result.rows_skipped}")
    print(f"  error    {result.rows_error}")
    if result.error_payload:
        print("  ── 에러 (최대 50건) ──")
        for e in result.error_payload[:10]:
            print(f"    row {e.row_index} [{e.error_code}] {e.error_msg}")
        if len(result.error_payload) > 10:
            print(f"    ... 외 {len(result.error_payload) - 10}건")

    if not args.dry_run and result.ingest_log_id:
        print(f"  ingest_log_id = {result.ingest_log_id}")

    return 0 if result.rows_error == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
