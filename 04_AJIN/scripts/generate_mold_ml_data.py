"""
금형 수명 ML 학습용 합성 데이터 생성기
- 바스텁 커브(Bathtub Curve) 기반 불량률 시뮬레이션
- 25건 실 금형 × 20 변형 = 500건 학습 데이터
- 금형 소재/제품 유형/보전 주기별 수명 패턴 차등화
"""

import numpy as np
import pandas as pd
import sqlite3
from pathlib import Path
from typing import List, Dict


OUTPUT_DIR = Path("data/mold_ml")
MOLD_DB = "data/equipment/mold_lifecycle.db"

# 금형 소재별 수명 계수 (소재가 수명에 미치는 영향)
MATERIAL_LIFE_FACTOR = {
    "SKD11": 1.0,       # 기준 (냉간 금형강)
    "SKD61": 1.15,      # 열간 금형강 — 내열 우수
    "SKH51": 0.9,       # 고속도강 — 경도 높으나 취성
    "S45C": 0.75,       # 탄소강 — 경제적이나 수명 짧음
    "NAK80": 1.1,       # 경면 가공용 — 정밀 금형
    "STAVAX": 1.2,      # 스테인리스 금형강 — 내식 우수
    "default": 1.0,
}

# 제품 유형별 금형 부하 계수 (높을수록 금형에 가혹)
PRODUCT_LOAD_FACTOR = {
    "EWP": 0.8,         # 정밀 가공 — 하중 낮음
    "CCH": 0.85,        # 냉각 플레이트 — 중하중
    "OBC": 0.9,         # 케이스 — 중하중
    "범퍼": 1.2,        # 대형 프레스 — 고하중
    "서브프레임": 1.3,    # 고강도강 — 최고하중
    "시트": 1.0,        # 일반
    "도어": 1.1,        # 대형
    "브레이크": 0.95,    # 정밀
    "DASH": 1.15,       # 대형 + 복잡 형상
    "default": 1.0,
}


def bathtub_defect_curve(
    shots: np.ndarray,
    max_life: int,
    material_factor: float = 1.0,
    load_factor: float = 1.0,
    maintenance_quality: float = 1.0,
    noise_std: float = 0.03,
    seed: int = None,
) -> np.ndarray:
    """
    바스텁 커브 기반 불량률 시뮬레이션

    3단계:
      1. 초기 고장기 (0~10%): 금형 세팅/조정 구간 — 불량률 높았다 감소
      2. 우발 고장기 (10~70%): 안정 운영 — 기저 불량률 유지
      3. 마모 고장기 (70~100%): 수명 말기 — 불량률 급증

    Args:
        shots: 타수 배열
        max_life: 설계 수명 (타수)
        material_factor: 소재 수명 계수 (높을수록 오래 사용)
        load_factor: 부하 계수 (높을수록 빨리 마모)
        maintenance_quality: 보전 품질 (0.7~1.3, 높을수록 수명 연장)
        noise_std: 불량률 노이즈 표준편차
    """
    if seed is not None:
        np.random.seed(seed)

    # 실효 수명 = 설계 수명 × 소재 × (1/부하) × 보전 품질
    effective_life = max_life * material_factor * (1.0 / load_factor) * maintenance_quality
    ratio = shots / effective_life

    defect_rates = np.zeros_like(shots, dtype=float)

    for i, r in enumerate(ratio):
        if r < 0:
            r = 0

        # 초기 고장기 (번인)
        early = 0.8 * np.exp(-15 * r)

        # 우발 고장기 (안정)
        base = 0.08 + 0.02 * load_factor

        # 마모 고장기 (말기)
        if r > 0.65:
            wear = 0.5 * np.exp(4.0 * (r - 0.65))
        else:
            wear = 0.0

        defect_rates[i] = early + base + wear

    # 노이즈 추가
    noise = np.random.normal(0, noise_std, len(shots))
    defect_rates = np.clip(defect_rates + noise, 0.01, 15.0)

    return np.round(defect_rates, 3)


def generate_training_data(n_variations: int = 20) -> pd.DataFrame:
    """
    기존 25건 금형 기반 합성 학습 데이터 생성

    각 금형마다 n_variations개의 "시점 스냅샷"을 생성:
      - 랜덤 타수 시점에서의 현재 상태를 캡처
      - 해당 시점에서의 잔여수명(정답)을 계산
    """
    # 기존 금형 데이터 로드
    real_molds = _load_real_molds()
    if not real_molds:
        real_molds = _generate_default_molds()

    records = []

    for mold in real_molds:
        mold_id = mold.get("id", mold.get("mold_id", ""))
        mold_name = mold.get("name", mold.get("mold_name", ""))
        max_life = mold.get("designed_life", mold.get("max_shots", 100000))
        material = mold.get("material", "SKD11")
        product = mold.get("product", mold.get("product_type", "default"))

        mat_factor = MATERIAL_LIFE_FACTOR.get(material, MATERIAL_LIFE_FACTOR["default"])
        load_factor = _get_load_factor(product)

        for v in range(n_variations):
            seed = hash(f"{mold_id}_{v}") % 100000

            # 보전 품질 랜덤 변형 (0.7 나쁨 ~ 1.3 우수)
            maint_quality = np.random.uniform(0.7, 1.3)

            # 랜덤 시점의 현재 타수 (5%~105% 범위)
            current_ratio = np.random.uniform(0.05, 1.05)
            current_shots = int(max_life * current_ratio)

            # 불량률 이력 시뮬레이션 (현재까지)
            shot_points = np.linspace(0, current_shots, 20)
            defect_history = bathtub_defect_curve(
                shot_points, max_life, mat_factor, load_factor, maint_quality,
                noise_std=0.04, seed=seed + v,
            )

            current_defect = float(defect_history[-1])

            # 최근 불량률 추이 (최근 5포인트 기울기)
            if len(defect_history) >= 5:
                recent_slope = float(np.polyfit(range(5), defect_history[-5:], 1)[0])
            else:
                recent_slope = 0.0

            # 불량률 이동평균 (최근 5)
            recent_avg = float(np.mean(defect_history[-5:]))

            # 보전 횟수 (사용률에 비례 + 랜덤)
            maint_count = max(0, int(current_ratio * 10 * maint_quality + np.random.randint(-2, 3)))

            # SPC 이상률 (합성) — 아이디어 ① 연계
            spc_anomaly_rate = max(0, 5.0 + current_defect * 3 + np.random.normal(0, 2))

            # ── 정답(label): 잔여수명 ──
            # 불량률 1% 초과 시점을 "실효 수명 끝"으로 정의
            effective_life = max_life * mat_factor * (1.0 / load_factor) * maint_quality
            full_curve = bathtub_defect_curve(
                np.arange(0, int(effective_life * 1.2), 500),
                max_life, mat_factor, load_factor, maint_quality,
                noise_std=0.01, seed=seed,
            )
            # 1% 초과하는 첫 번째 인덱스
            exceed_indices = np.where(full_curve > 1.0)[0]
            if len(exceed_indices) > 0:
                failure_shots = int(exceed_indices[0] * 500)
            else:
                failure_shots = int(effective_life)

            remaining_life = max(0, failure_shots - current_shots)

            records.append({
                "mold_id": mold_id,
                "mold_name": mold_name,
                "product_type": product,
                "material": material,
                "designed_life": max_life,
                "current_shots": current_shots,
                "usage_ratio": round(current_shots / max_life, 3),
                "current_defect_rate": round(current_defect, 3),
                "recent_defect_avg": round(recent_avg, 3),
                "defect_slope": round(recent_slope, 5),
                "maintenance_count": maint_count,
                "maintenance_quality": round(maint_quality, 2),
                "material_factor": mat_factor,
                "load_factor": load_factor,
                "spc_anomaly_rate": round(spc_anomaly_rate, 1),
                # 정답
                "remaining_life": remaining_life,
                "failure_shots": failure_shots,
            })

    df = pd.DataFrame(records)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "mold_training_data.csv"
    df.to_csv(output_path, index=False)
    print(f"학습 데이터 생성: {len(df)}건 → {output_path}")
    print(f"  잔여수명 범위: {df['remaining_life'].min():,} ~ {df['remaining_life'].max():,} 타")
    print(f"  평균 잔여수명: {df['remaining_life'].mean():,.0f} 타")

    return df


def _load_real_molds() -> List[Dict]:
    """기존 mold_lifecycle.db에서 금형 데이터 로드"""
    if not Path(MOLD_DB).exists():
        return []
    try:
        conn = sqlite3.connect(MOLD_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM molds").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _generate_default_molds() -> List[Dict]:
    """DB 없을 경우 기본 금형 25건 생성"""
    molds = []
    products = ["EWP", "CCH", "OBC", "범퍼", "서브프레임", "시트", "도어", "브레이크", "DASH"]
    materials = ["SKD11", "SKD61", "SKH51", "S45C", "NAK80"]
    for i in range(25):
        prod = products[i % len(products)]
        mat = materials[i % len(materials)]
        molds.append({
            "id": i + 1,
            "name": f"{prod}-M-{i+1:03d}",
            "product": prod,
            "material": mat,
            "designed_life": np.random.choice([50000, 80000, 100000, 120000, 150000]),
        })
    return molds


def _get_load_factor(product: str) -> float:
    """제품명에서 부하 계수 추출"""
    for key, factor in PRODUCT_LOAD_FACTOR.items():
        if key in product:
            return factor
    return PRODUCT_LOAD_FACTOR["default"]


if __name__ == "__main__":
    print("금형 수명 ML 합성 데이터 생성 시작...")
    df = generate_training_data(n_variations=20)
    print("완료!")
