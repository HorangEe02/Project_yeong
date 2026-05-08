"""
SPC ML 학습용 합성 시계열 데이터 생성기
- 5공정별 2,000포인트 생성
- 정상 구간 + 5가지 이상 패턴 주입
- 각 포인트에 라벨 부여 (normal/anomaly + 이상 유형)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta


OUTPUT_DIR = Path("data/spc_ml")

# 5공정 사양 정의 (기존 SPC 데이터 기준)
PROCESS_SPECS = {
    "ewp_housing_bore": {
        "name": "EWP 하우징 내경",
        "nominal": 25.000,    # 규격 중심값 (mm)
        "usl": 25.050,        # 규격 상한
        "lsl": 24.950,        # 규격 하한
        "normal_std": 0.012,  # 정상 상태 표준편차 (Cpk ≈ 1.4)
        "unit": "mm",
    },
    "cch_plate_thickness": {
        "name": "CCH 냉각플레이트 두께",
        "nominal": 3.200,
        "usl": 3.230,
        "lsl": 3.170,
        "normal_std": 0.006,  # Cpk ≈ 1.67
        "unit": "mm",
    },
    "obc_case_flatness": {
        "name": "OBC 케이스 평탄도",
        "nominal": 0.100,
        "usl": 0.150,
        "lsl": 0.050,
        "normal_std": 0.016,  # Cpk ≈ 1.05 (기존 C등급)
        "unit": "mm",
    },
    "bumper_nugget_diameter": {
        "name": "범퍼빔 너겟 직경",
        "nominal": 6.500,
        "usl": 6.800,
        "lsl": 6.200,
        "normal_std": 0.083,  # Cpk ≈ 1.2
        "unit": "mm",
    },
    "seatrail_hole_position": {
        "name": "시트레일 홀 위치도",
        "nominal": 0.000,
        "usl": 0.100,
        "lsl": -0.100,
        "normal_std": 0.022,  # Cpk ≈ 1.52
        "unit": "mm",
    },
}


def generate_process_data(
    spec: dict,
    n_points: int = 2000,
    anomaly_ratio: float = 0.12,
    seed: int = None,
) -> pd.DataFrame:
    """
    단일 공정의 합성 시계열 생성

    이상 패턴 5종:
      1. sudden_shift — 갑작스러운 평균 이동 (공구 교체 누락, 소재 로트 변경)
      2. gradual_drift — 서서히 평균 이동 (공구 마모, 열 팽창)
      3. variance_increase — 분산 증가 (클램핑 불량, 베어링 마모)
      4. spike — 돌발 이상값 (이물 혼입, 측정 오류)
      5. cyclic_pattern — 주기적 변동 (온도 사이클, 냉각수 온도 변화)
    """
    if seed is not None:
        np.random.seed(seed)

    nominal = spec["nominal"]
    std = spec["normal_std"]
    n_anomaly = int(n_points * anomaly_ratio)
    n_normal = n_points - n_anomaly

    # 정상 데이터
    normal_data = np.random.normal(nominal, std, n_normal)
    normal_labels = ["normal"] * n_normal
    normal_types = [""] * n_normal

    # 이상 데이터 (5종 균등 배분)
    n_each = max(1, n_anomaly // 5)
    anomaly_data = []
    anomaly_labels = []
    anomaly_types = []

    # 1) Sudden shift — 평균이 갑자기 1.5~3σ 이동
    shift_dir = np.random.choice([-1, 1])
    shift_magnitude = np.random.uniform(1.5, 3.0) * std
    shifted = np.random.normal(nominal + shift_dir * shift_magnitude, std, n_each)
    anomaly_data.extend(shifted)
    anomaly_labels.extend(["anomaly"] * n_each)
    anomaly_types.extend(["sudden_shift"] * n_each)

    # 2) Gradual drift — 서서히 이동 (선형 추세)
    drift_slope = np.random.uniform(0.5, 2.0) * std / 50  # 50포인트당 0.5~2σ 이동
    drift_base = np.random.normal(nominal, std, n_each)
    drift_trend = np.arange(n_each) * drift_slope * np.random.choice([-1, 1])
    drifted = drift_base + drift_trend
    anomaly_data.extend(drifted)
    anomaly_labels.extend(["anomaly"] * n_each)
    anomaly_types.extend(["gradual_drift"] * n_each)

    # 3) Variance increase — 분산 2~4배 증가
    var_multiplier = np.random.uniform(2.0, 4.0)
    high_var = np.random.normal(nominal, std * var_multiplier, n_each)
    anomaly_data.extend(high_var)
    anomaly_labels.extend(["anomaly"] * n_each)
    anomaly_types.extend(["variance_increase"] * n_each)

    # 4) Spike — 4~6σ 이상 돌발값
    spike_values = nominal + np.random.choice([-1, 1], n_each) * np.random.uniform(4, 6, n_each) * std
    anomaly_data.extend(spike_values)
    anomaly_labels.extend(["anomaly"] * n_each)
    anomaly_types.extend(["spike"] * n_each)

    # 5) Cyclic pattern — 사인파 주기적 변동
    t = np.arange(n_each)
    cycle_amplitude = np.random.uniform(1.5, 3.0) * std
    cycle_period = np.random.uniform(20, 50)
    cyclic = nominal + cycle_amplitude * np.sin(2 * np.pi * t / cycle_period) + np.random.normal(0, std * 0.5, n_each)
    anomaly_data.extend(cyclic)
    anomaly_labels.extend(["anomaly"] * n_each)
    anomaly_types.extend(["cyclic_pattern"] * n_each)

    # 전체 결합
    all_values = np.concatenate([normal_data, np.array(anomaly_data)])
    all_labels = normal_labels + anomaly_labels
    all_types = normal_types + anomaly_types

    # 시간순 셔플 (실제 생산처럼 이상이 군집 발생하도록 부분 셔플)
    indices = np.arange(len(all_values))
    # 블록 단위로 셔플 (50포인트 블록 → 블록 순서만 변경)
    block_size = 50
    blocks = [indices[i:i+block_size] for i in range(0, len(indices), block_size)]
    np.random.shuffle(blocks)
    shuffled_indices = np.concatenate(blocks)

    all_values = all_values[shuffled_indices]
    all_labels = [all_labels[i] for i in shuffled_indices]
    all_types = [all_types[i] for i in shuffled_indices]

    # 타임스탬프 생성 (1분 간격)
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    timestamps = [base_time + timedelta(minutes=i) for i in range(len(all_values))]

    df = pd.DataFrame({
        "timestamp": timestamps,
        "value": np.round(all_values, 4),
        "label": all_labels,
        "anomaly_type": all_types,
        "usl": spec["usl"],
        "lsl": spec["lsl"],
        "nominal": spec["nominal"],
    })

    return df


def inject_nelson_patterns(df: pd.DataFrame, spec: dict, process_id: str) -> pd.DataFrame:
    """v3.4: 셔플 완료된 DataFrame에 Nelson Rule 위반 패턴을 의도적으로 오버라이드.

    공정별 전략:
      - ewp_housing_bore: Rule 2 (9점 편향) + Rule 3 (6점 추세) — 데모 주력
      - cch_plate_thickness: Rule 1 (UCL 이탈 1점) — 직관적 이상
      - obc_case_flatness: 정상 유지 (비교 기준)
      - bumper_nugget_diameter: Rule 5 (2σ 빈발 패턴)
      - seatrail_hole_position: Rule 3 (추세 패턴)
    """
    modified = df.copy()
    nominal = spec["nominal"]
    std = spec["normal_std"]
    n = len(modified)

    if process_id == "ewp_housing_bore":
        # Rule 2: idx 20~28에 9점 연속 중심선 상방 (관리 한계 안, 편향)
        for i in range(20, min(29, n)):
            modified.at[i, "value"] = round(nominal + std * np.random.uniform(0.3, 0.8), 4)
            modified.at[i, "label"] = "anomaly"
            modified.at[i, "anomaly_type"] = "nelson_rule2_bias"
        # Rule 3: idx 35~40에 6점 연속 증가 (공구 마모 시뮬레이션)
        base_val = nominal - std * 0.2
        for j, idx in enumerate(range(35, min(41, n))):
            modified.at[idx, "value"] = round(base_val + std * 0.25 * j, 4)
            modified.at[idx, "label"] = "anomaly"
            modified.at[idx, "anomaly_type"] = "nelson_rule3_trend"

    elif process_id == "cch_plate_thickness":
        # Rule 1: idx 45에 UCL 이탈 1점 (가장 직관적)
        if n > 45:
            ucl = nominal + 3 * std
            modified.at[45, "value"] = round(ucl + std * 0.3, 4)  # UCL 약간 초과
            modified.at[45, "label"] = "anomaly"
            modified.at[45, "anomaly_type"] = "nelson_rule1_ucl_breach"

    elif process_id == "obc_case_flatness":
        pass  # 정상 유지 (건강한 공정 비교 기준)

    elif process_id == "bumper_nugget_diameter":
        # Rule 5: 연속 3점 중 2점이 같은 쪽 2σ 이상 (idx 50~55)
        # v3.4 fix: 같은 방향(+)으로 고정해야 Nelson Rule 5 트리거
        for i in range(50, min(56, n)):
            if i % 3 != 2:  # 3점 중 2점을 2σ 이상 (같은 쪽)
                modified.at[i, "value"] = round(nominal + std * np.random.uniform(2.1, 2.5), 4)
                modified.at[i, "label"] = "anomaly"
                modified.at[i, "anomaly_type"] = "nelson_rule5_2sigma"

    elif process_id == "seatrail_hole_position":
        # Rule 3: idx 60~65에 6점 연속 감소 (공구 마모)
        base_val = nominal + std * 0.3
        for j, idx in enumerate(range(60, min(66, n))):
            modified.at[idx, "value"] = round(base_val - std * 0.2 * j, 4)
            modified.at[idx, "label"] = "anomaly"
            modified.at[idx, "anomaly_type"] = "nelson_rule3_trend"

    return modified


def generate_all_processes(n_points: int = 2000):
    """5공정 전체 합성 데이터 생성"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    for process_id, spec in PROCESS_SPECS.items():
        df = generate_process_data(spec, n_points=n_points, seed=hash(process_id) % 10000)
        # v3.4: 셔플 완료 후 Nelson 패턴 오버라이드
        df = inject_nelson_patterns(df, spec, process_id)
        output_path = OUTPUT_DIR / f"{process_id}.csv"
        df.to_csv(output_path, index=False)

        n_anomaly = (df["label"] == "anomaly").sum()
        print(f"  {spec['name']}: {len(df)}포인트 (이상: {n_anomaly}건, {n_anomaly/len(df)*100:.1f}%)")
        total += len(df)

    # v3.4: 캐시된 ML 모델 삭제 (재학습 유도)
    models_dir = OUTPUT_DIR / "models"
    if models_dir.exists():
        import shutil
        shutil.rmtree(models_dir)
        print(f"\n캐시 삭제: {models_dir}/ (다음 실행 시 모델 재학습)")

    print(f"\n전체: {total}포인트 → {OUTPUT_DIR}/")
    return total


if __name__ == "__main__":
    print("SPC ML 합성 데이터 생성 시작...")
    generate_all_processes()
    print("완료!")
