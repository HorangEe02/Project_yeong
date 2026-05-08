"""
v3.5: SPC 공정 데이터 생성기

정규분포 기반 통계적 시뮬레이션으로 현실적인 SPC 측정 데이터를 생성한다.
Nelson 8 Rules 위반 시나리오, 트렌드, 이상치 주입을 지원한다.
"""
from __future__ import annotations

import csv
import io
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class SPCGeneratorConfig:
    """SPC 데이터 생성 설정"""
    n_samples: int = 200
    # 공정 규격
    target: float = 0.0
    usl: float = 1.0
    lsl: float = -1.0
    # 공정 능력 (sigma 계산에 사용)
    cpk_target: float = 1.33  # 1.33=양호, 1.0=경계, 0.67=불량
    # 시나리오 주입
    inject_trend: bool = False          # 선형 드리프트
    trend_slope: float = 0.001          # 샘플당 이동량
    inject_shift: bool = False          # 평균 이동 (Nelson Rule 2)
    shift_at_sample: int = 100          # 이동 시작 시점
    shift_amount: float = 0.5           # sigma 단위 이동량
    inject_outliers: bool = False       # 이상치 주입
    outlier_rate: float = 0.02          # 이상치 비율 (2%)
    outlier_magnitude: float = 3.0      # sigma 단위 크기
    inject_stratification: bool = False # 층화 (Nelson Rule 3: 중심선 근처 집중)
    inject_oscillation: bool = False    # 진동 패턴 (Nelson Rule 5)
    seed: int | None = None             # 재현성을 위한 시드


def generate_spc_data(config: SPCGeneratorConfig) -> list[float]:
    """설정에 따라 SPC 측정 데이터를 생성한다.

    Returns:
        list of float: 측정값 리스트
    """
    rng = random.Random(config.seed)

    # 공정 sigma 계산: Cpk = min(USL-mu, mu-LSL) / (3*sigma)
    # target이 중앙이라 가정: sigma = (USL - target) / (3 * Cpk)
    half_range = min(config.usl - config.target, config.target - config.lsl)
    sigma = half_range / (3.0 * config.cpk_target) if config.cpk_target > 0 else half_range / 3.0

    values: list[float] = []

    for i in range(config.n_samples):
        # 기본 정규분포
        mean = config.target

        # 트렌드 주입
        if config.inject_trend:
            mean += config.trend_slope * i

        # 평균 이동 주입
        if config.inject_shift and i >= config.shift_at_sample:
            mean += config.shift_amount * sigma

        # 층화 패턴 (sigma 축소 → 중심선 집중)
        effective_sigma = sigma
        if config.inject_stratification:
            effective_sigma = sigma * 0.3

        # 진동 패턴
        oscillation = 0.0
        if config.inject_oscillation:
            oscillation = sigma * 1.5 * math.sin(2 * math.pi * i / 8)

        value = rng.gauss(mean + oscillation, effective_sigma)

        # 이상치 주입
        if config.inject_outliers and rng.random() < config.outlier_rate:
            direction = rng.choice([-1, 1])
            value = config.target + direction * config.outlier_magnitude * sigma

        values.append(round(value, 4))

    return values


def generate_spc_csv_bytes(
    config: SPCGeneratorConfig,
    process_name: str = "공정",
    part_number: str = "AJ-XXX-000",
    unit: str = "mm",
) -> bytes:
    """SPC 데이터를 CSV 바이트로 생성한다 (기존 spc_samples 포맷 호환)."""
    values = generate_spc_data(config)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["sample", "value", "unit", "part_number", "process"])
    for i, val in enumerate(values, start=1):
        writer.writerow([i, val, unit, part_number, process_name])

    return buf.getvalue().encode("utf-8-sig")


def generate_and_save(
    process_id: str,
    config: SPCGeneratorConfig,
    process_name: str = "공정",
    part_number: str = "AJ-XXX-000",
    unit: str = "mm",
    output_dir: str = "data/spc_ml",
) -> Path:
    """SPC 데이터를 생성하고 CSV 파일로 저장한다."""
    values = generate_spc_data(config)
    out_path = Path(output_dir) / f"{process_id}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample", "value", "unit", "part_number", "process"])
        for i, val in enumerate(values, start=1):
            writer.writerow([i, val, unit, part_number, process_name])

    return out_path


def regenerate_all_samples(n_samples: int = 200, seed: int = 42):
    """모든 기존 SPC 공정에 대해 샘플 데이터를 재생성한다.

    spc_meta.json의 5개 공정 + spc_ml 디렉토리의 데이터를 업데이트.
    """
    meta_path = Path("data/spc_samples/spc_meta.json")
    if not meta_path.exists():
        return []

    with open(meta_path, encoding="utf-8") as f:
        processes = json.load(f)

    results = []
    for i, proc in enumerate(processes):
        config = SPCGeneratorConfig(
            n_samples=n_samples,
            target=proc["target"],
            usl=proc["usl"],
            lsl=proc["lsl"],
            cpk_target=1.33 + random.Random(seed + i).uniform(-0.3, 0.3),
            seed=seed + i,
            # 일부 공정에 시나리오 주입 (다양한 패턴 시연용)
            inject_trend=(i == 1),       # CCH: 트렌드
            inject_shift=(i == 3),       # 범퍼빔: 평균 이동
            inject_outliers=(i == 2),    # OBC: 이상치
        )

        # spc_samples용 (기존 호환)
        filename = proc["filename"]
        values = generate_spc_data(config)
        out_path = Path("data/spc_samples") / filename
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["sample", "value", "unit", "part_number", "process"])
            for j, val in enumerate(values, start=1):
                writer.writerow([j, val, proc["unit"], proc["part_number"], proc["name"]])

        # spc_ml용 (대시보드에서 사용)
        # process_id는 파일명에서 추출
        process_id = filename.replace("spc_", "").replace(".csv", "")
        ml_path = Path("data/spc_ml") / f"{process_id}.csv"
        ml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ml_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["sample", "value", "unit", "part_number", "process"])
            for j, val in enumerate(values, start=1):
                writer.writerow([j, val, proc["unit"], proc["part_number"], proc["name"]])

        # meta 업데이트
        proc["n_samples"] = n_samples
        results.append((proc["name"], n_samples, out_path))

    # spc_meta.json 업데이트
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(processes, f, ensure_ascii=False, indent=2)

    return results
