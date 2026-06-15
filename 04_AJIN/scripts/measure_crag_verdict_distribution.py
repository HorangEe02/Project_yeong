"""CRAG verdict 분포 측정 — production audit log 기반 threshold tuning 데이터 수집.

출처: docs/RAG_ENHANCEMENT_PLAN.md §11 #4 후속 + §12 후속 튜닝.
사용자 Goal: "production verdict 분포 측정 후 upper=0.60 검토".

backend/routers/search.py 의 _audit_search_event() 가 'crag=<verdict>(<score>)' 형식으로
audit log 에 기록한다 (PR #10 변경). 본 스크립트는 그 로그를 파싱하여:
  1. verdict 별 빈도 (correct/ambiguous/incorrect)
  2. top_score 분포 (min/max/avg/median/p25/p75/p90)
  3. 임계치 변경 시뮬레이션 (upper=0.60 vs 0.70 vs 0.65)

production audit log 경로:
- Cloud Run: gcloud logging 에서 추출 (별도 단계). 본 스크립트는 추출된 JSON/text 파일 전제.
- 로컬: data/_audit/audit.log 또는 backend stdout 캡쳐.

사용:
    python scripts/measure_crag_verdict_distribution.py \\
        --log /path/to/audit.log \\
        --output data/eval/crag_distribution.json

production gcloud 추출 예시:
    gcloud logging read 'resource.type=cloud_run_revision AND textPayload:"crag="' \\
      --limit 10000 --format='value(textPayload)' > /tmp/audit_crag.log
    python scripts/measure_crag_verdict_distribution.py --log /tmp/audit_crag.log
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_CRAG_PATTERN = re.compile(r"crag=(correct|ambiguous|incorrect)\(([0-9.]+)\)")


def parse_audit_log(path: Path) -> list[tuple[str, float]]:
    """audit log line 들에서 'crag=verdict(score)' 추출.

    Returns:
        list of (verdict, score) tuples.
    """
    events: list[tuple[str, float]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            for match in _CRAG_PATTERN.finditer(line):
                verdict = match.group(1)
                try:
                    score = float(match.group(2))
                except ValueError:
                    continue
                events.append((verdict, score))
    return events


def compute_score_distribution(scores: list[float]) -> dict[str, float]:
    """score 분포 통계."""
    if not scores:
        return {"count": 0}
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    return {
        "count": n,
        "min": min(scores),
        "max": max(scores),
        "avg": statistics.mean(scores),
        "median": statistics.median(scores),
        "p25": sorted_scores[int(n * 0.25)],
        "p75": sorted_scores[int(n * 0.75)],
        "p90": sorted_scores[int(n * 0.90)] if n >= 10 else sorted_scores[-1],
        "p95": sorted_scores[int(n * 0.95)] if n >= 20 else sorted_scores[-1],
    }


def simulate_thresholds(
    events: list[tuple[str, float]],
    upper_candidates: list[float],
    lower: float = 0.40,
) -> dict[str, dict[str, int]]:
    """다른 upper threshold 후보들에 대한 verdict 재분포 시뮬레이션.

    예: upper=0.70 (현재) → 0.60 변경 시 ambiguous 가 correct 로 얼마나 이동?
    """
    scores = [s for _, s in events]
    result: dict[str, dict[str, int]] = {}
    for upper in upper_candidates:
        counter = Counter()
        for s in scores:
            if s >= upper:
                counter["correct"] += 1
            elif s >= lower:
                counter["ambiguous"] += 1
            else:
                counter["incorrect"] += 1
        result[f"upper={upper:.2f}_lower={lower:.2f}"] = dict(counter)
    return result


def print_report(events: list[tuple[str, float]], thresholds: dict[str, dict[str, int]]) -> None:
    print()
    print("=" * 70)
    print("CRAG Verdict Distribution Report")
    print("=" * 70)
    print(f"총 audit 이벤트: {len(events)}건")
    print()

    # 1. 현재 verdict 별 빈도
    verdict_counts = Counter(v for v, _ in events)
    print("[1] 현재 verdict 분포 (config 기본 upper=0.70, lower=0.40):")
    for v in ("correct", "ambiguous", "incorrect"):
        n = verdict_counts.get(v, 0)
        pct = n / len(events) * 100 if events else 0
        print(f"  {v:<11s} {n:>6d}건  ({pct:5.1f}%)")
    print()

    # 2. score 분포 (전체 + verdict 별)
    all_scores = [s for _, s in events]
    print(f"[2] top_score 분포 (n={len(all_scores)}):")
    dist = compute_score_distribution(all_scores)
    for k in ("min", "p25", "median", "avg", "p75", "p90", "p95", "max"):
        if k in dist:
            print(f"  {k:<7s} {dist[k]:.3f}")
    print()

    # 3. 임계치 변경 시뮬레이션
    print("[3] upper threshold 변경 시뮬레이션 (lower=0.40 고정):")
    print(f"  {'threshold':<32s} {'correct':>8s} {'ambig':>8s} {'incor':>8s}")
    print("  " + "-" * 60)
    for label, counts in thresholds.items():
        c = counts.get("correct", 0)
        a = counts.get("ambiguous", 0)
        i = counts.get("incorrect", 0)
        print(f"  {label:<32s} {c:>8d} {a:>8d} {i:>8d}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="CRAG verdict 분포 측정")
    parser.add_argument("--log", required=True, help="audit log 파일 경로")
    parser.add_argument(
        "--output",
        default="data/eval/crag_distribution.json",
        help="결과 JSON 저장 경로",
    )
    parser.add_argument(
        "--upper-candidates",
        default="0.60,0.65,0.70,0.75",
        help="시뮬레이션할 upper threshold 후보 (쉼표 구분)",
    )
    parser.add_argument("--lower", type=float, default=0.40, help="lower threshold (고정)")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"audit log 파일 없음: {log_path}", file=sys.stderr)
        return 1

    events = parse_audit_log(log_path)
    if not events:
        print("crag= 패턴 매치 0건 — audit log 형식 확인 필요", file=sys.stderr)
        return 1

    upper_candidates = [float(u.strip()) for u in args.upper_candidates.split(",") if u.strip()]
    thresholds = simulate_thresholds(events, upper_candidates, lower=args.lower)

    # 결과 저장
    payload: dict[str, Any] = {
        "total_events": len(events),
        "verdict_counts": dict(Counter(v for v, _ in events)),
        "score_distribution": compute_score_distribution([s for _, s in events]),
        "threshold_simulations": thresholds,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"결과 저장: {output_path}")
    print()

    print_report(events, thresholds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
