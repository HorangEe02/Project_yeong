#!/usr/bin/env python3
"""SPC 시연용 시드 스크립트 — Nelson 8 규칙 위반을 보장하는 데모 데이터 생성.

CRAWLER_TIMEOUT_DIAGNOSIS의 P0 후속 작업으로, /equipment 첫 진입 시
지정한 공정 (기본 EWP) 의 신호등이 빨강 (R1 위반) 으로 보이도록 시드한다.

사용 예:
    python3 scripts/seed_spc_demo.py --process EWP --inject r1
    python3 scripts/seed_spc_demo.py --process CCH --inject r2
    python3 scripts/seed_spc_demo.py --reset                  # 정상 데이터로 복구

Nelson Rule 매핑:
    r1 — 한 점이 ±3σ 초과       → inject_outliers=True (강제)
    r2 — 9점 연속 한쪽          → inject_shift=True
    r3 — 6점 연속 증가/감소     → inject_trend=True
    r5 — 3점 중 2점이 ±2σ 초과  → inject_oscillation=True
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from features.equipment.spc_data_generator import (  # noqa: E402
    SPCGeneratorConfig,
    generate_spc_data,
)
from core.data_lineage import write_source_manifest  # noqa: E402


INJECT_FLAGS = {
    # outlier_magnitude 5.0σ — cpk 기반 inject sigma < 측정 sigma 차이를 보정해
    # Nelson R1(측정 ±3σ 초과)이 실제로 트리거되도록 보장
    "r1": {"inject_outliers": True, "outlier_rate": 0.05, "outlier_magnitude": 5.0},
    "r2": {"inject_shift": True, "shift_at_sample": 80, "shift_amount": 1.5},
    "r3": {"inject_trend": True, "trend_slope": 0.003},
    "r5": {"inject_oscillation": True},
}


def _resolve_process(name: str, processes: list[dict]) -> dict | None:
    name_l = name.lower()
    for proc in processes:
        if proc["name"].lower() == name_l or proc.get("part_number", "").lower().startswith(name_l):
            return proc
        # filename 매칭 (spc_ewp.csv → ewp)
        fname = proc.get("filename", "").lower()
        if fname.startswith(f"spc_{name_l}"):
            return proc
    return None


def _write_csv(path: Path, values: list[float], proc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample", "value", "unit", "part_number", "process"])
        for i, val in enumerate(values, start=1):
            writer.writerow([i, val, proc["unit"], proc["part_number"], proc["name"]])


def seed(process: str, inject: str, n_samples: int = 200, seed_val: int = 42) -> int:
    meta_path = REPO_ROOT / "data" / "spc_samples" / "spc_meta.json"
    if not meta_path.exists():
        print(f"✗ spc_meta.json 없음: {meta_path}. 먼저 seed_synthetic_data.py 실행 필요.")
        return 2

    with open(meta_path, encoding="utf-8") as f:
        processes = json.load(f)

    proc = _resolve_process(process, processes)
    if proc is None:
        print(f"✗ 공정 '{process}' 미발견. 사용 가능: {[p['name'] for p in processes]}")
        return 3

    flags = INJECT_FLAGS.get(inject)
    if flags is None:
        print(f"✗ inject '{inject}' 미지원. 사용 가능: {list(INJECT_FLAGS.keys())}")
        return 4

    config = SPCGeneratorConfig(
        n_samples=n_samples,
        target=proc["target"],
        usl=proc["usl"],
        lsl=proc["lsl"],
        cpk_target=1.33,
        seed=seed_val,
        **flags,
    )
    values = generate_spc_data(config)

    # spc_samples + spc_ml 동시 갱신 (대시보드 양쪽 데이터 소스)
    fname = proc["filename"]
    process_id = fname.replace("spc_", "").replace(".csv", "")
    samples_path = REPO_ROOT / "data" / "spc_samples" / fname
    ml_path = REPO_ROOT / "data" / "spc_ml" / f"{process_id}.csv"

    _write_csv(samples_path, values, proc)
    _write_csv(ml_path, values, proc)
    for path in (samples_path, ml_path):
        write_source_manifest(
            path,
            data_class="synthetic",
            source_system="seed_equipment",
            source_label=f"seed_spc_demo:{inject}",
            extra={"process": proc["name"], "samples": n_samples},
        )

    proc["n_samples"] = n_samples
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(processes, f, ensure_ascii=False, indent=2)

    print(f"✓ '{proc['name']}' 공정에 Nelson {inject.upper()} 위반 패턴 주입 완료")
    print(f"  파일: {samples_path.relative_to(REPO_ROOT)}")
    print(f"        {ml_path.relative_to(REPO_ROOT)}")
    print(f"  샘플 수: {n_samples}, 시드: {seed_val}")
    return 0


def reset(n_samples: int = 200, seed_val: int = 42) -> int:
    """모든 공정을 정상 분포로 복구 (시연 후 정리)."""
    from features.equipment.spc_data_generator import regenerate_all_samples
    results = regenerate_all_samples(n_samples=n_samples, seed=seed_val)
    for item in results:
        paths: list[Path] = []
        if isinstance(item, dict) and item.get("path"):
            paths.append(Path(item["path"]))
        elif isinstance(item, tuple) and len(item) >= 3:
            paths.append(Path(item[2]))
            process_id = Path(item[2]).name.replace("spc_", "").replace(".csv", "")
            paths.append(REPO_ROOT / "data" / "spc_ml" / f"{process_id}.csv")
        for path in paths:
            if path.exists():
                write_source_manifest(
                    path,
                    data_class="synthetic",
                    source_system="seed_equipment",
                    source_label="seed_spc_demo:reset",
                    extra={"samples": n_samples},
                )
    print(f"✓ 정상 데이터로 복구: {len(results)}개 공정 갱신")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--process", default="EWP", help="대상 공정 (기본: EWP)")
    p.add_argument("--inject", default="r1", choices=list(INJECT_FLAGS.keys()),
                   help="주입할 Nelson 규칙 (기본: r1)")
    p.add_argument("--samples", type=int, default=200, help="샘플 수 (기본: 200)")
    p.add_argument("--seed", type=int, default=42, help="난수 시드 (기본: 42)")
    p.add_argument("--reset", action="store_true", help="정상 데이터로 복구")
    args = p.parse_args()

    if args.reset:
        return reset(n_samples=args.samples, seed_val=args.seed)
    return seed(process=args.process, inject=args.inject,
                n_samples=args.samples, seed_val=args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
