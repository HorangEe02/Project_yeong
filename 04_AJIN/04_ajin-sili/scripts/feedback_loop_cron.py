#!/usr/bin/env python3
"""P3 D12 — Feedback Loop 자동 재학습 cron.

월 1회 실행 (Cloud Scheduler 또는 cron):
  0 0 1 * *   python3 scripts/feedback_loop_cron.py

수동 실행 (관리자):
  python3 scripts/feedback_loop_cron.py --window=30 --min=5

옵션:
  --window=N      누적 분석 윈도우 (기본 30일)
  --min=N         자동 적용 최소 횟수 (기본 5회)
  --dry-run       제안만, 적용 안 함
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 프로젝트 루트 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Feedback Loop 자동 재학습")
    parser.add_argument("--window", type=int, default=30, help="분석 윈도우 (일)")
    parser.add_argument("--min", type=int, default=5, dest="min_occ",
                        help="자동 적용 최소 횟수")
    parser.add_argument("--dry-run", action="store_true",
                        help="제안만 출력, 파일 갱신 안 함")
    args = parser.parse_args()

    from features.compliance.feedback_loop import apply_aggregated_rules

    out = apply_aggregated_rules(
        window_days=args.window,
        min_occurrences=args.min_occ,
        dry_run=args.dry_run,
    )

    print("Feedback Loop 결과:")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if not args.dry_run:
        added = len(out.get("added_dept_mappings", []))
        fewshot = out.get("fewshot_added", 0)
        if added or fewshot:
            # Slack 알림 (선택)
            try:
                from features.compliance.notify_slack import route as slack_route
                slack_route({
                    "grade": "MEDIUM",
                    "item_title": f"[D12 자동재학습] 부서매핑 {added}건 / fewshot {fewshot}건 갱신",
                    "summary_ko": f"window={args.window}일, min={args.min_occ}회 — audit log: {out.get('audit_log_path')}",
                    "change_type": "modified",
                }, change_id=None)
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
