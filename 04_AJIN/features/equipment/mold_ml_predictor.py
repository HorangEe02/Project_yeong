"""
금형 수명 XGBoost 예측 엔진
- 바스텁 커브 합성 데이터 기반 학습
- 잔여수명(타수) 회귀 예측
- Feature Importance (SHAP-like) 요인 분석
- 교체 스케줄 자동 생성
"""

import numpy as np
import pandas as pd
import pickle
import sqlite3
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date, timedelta

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error

import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    from sklearn.ensemble import GradientBoostingRegressor


ML_DATA_DIR = Path("data/mold_ml")
MODEL_PATH = ML_DATA_DIR / "xgb_mold_life.pkl"
MOLD_DB = "data/equipment/mold_lifecycle.db"

# 학습에 사용할 특성 (feature) 목록
FEATURE_COLS = [
    "usage_ratio",            # 사용률 (0~1+)
    "current_defect_rate",    # 현재 불량률 (%)
    "recent_defect_avg",      # 최근 5포인트 불량률 평균
    "defect_slope",           # 불량률 기울기 (추세)
    "maintenance_count",      # 보전 횟수
    "material_factor",        # 소재 수명 계수
    "load_factor",            # 부하 계수
    "spc_anomaly_rate",       # SPC 이상률 (아이디어 ① 연계)
    "designed_life",          # 설계 수명
    "current_shots",          # 현재 타수
]

FEATURE_LABELS_KR = {
    "usage_ratio": "사용률",
    "current_defect_rate": "현재 불량률",
    "recent_defect_avg": "최근 불량률 평균",
    "defect_slope": "불량률 추세(기울기)",
    "maintenance_count": "보전 횟수",
    "material_factor": "소재 수명 계수",
    "load_factor": "제품 부하 계수",
    "spc_anomaly_rate": "SPC 이상률",
    "designed_life": "설계 수명",
    "current_shots": "현재 타수",
}

TARGET_COL = "remaining_life"

DAILY_SHOTS_ESTIMATE = 500  # 일일 평균 타수


@dataclass
class MoldPredictionResult:
    """금형 수명 예측 결과"""
    mold_id: str
    mold_name: str
    current_shots: int
    designed_life: int
    predicted_remaining: int       # XGBoost 예측 잔여수명 (타수)
    predicted_failure_shots: int   # 예측 고장 시점 (누적 타수)
    predicted_replacement_date: str # 예상 교체일
    confidence_interval: Tuple[int, int]  # 95% 신뢰구간 (하한, 상한)
    risk_level: str                # "critical" / "warning" / "normal"
    top_factors: List[Dict]        # 수명에 영향을 미치는 상위 요인
    current_defect_rate: float
    usage_ratio: float


@dataclass
class ModelMetrics:
    """모델 평가 지표"""
    mae: float           # Mean Absolute Error (타수)
    rmse: float          # Root Mean Squared Error
    r2: float            # 결정계수 R²
    train_size: int
    test_size: int
    feature_importance: Dict[str, float]


class MoldLifeXGBPredictor:
    """XGBoost 기반 금형 수명 예측기"""

    def __init__(self):
        self.model = None
        self.metrics: Optional[ModelMetrics] = None
        self._is_trained = False

    def train(self, data_path: str = None, force: bool = False) -> ModelMetrics:
        """
        모델 학습

        Args:
            data_path: CSV 경로 (None이면 기본 경로)
            force: True면 캐시 무시하고 재학습
        """
        # 캐시 로드 시도
        if not force and MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    cached = pickle.load(f)
                self.model = cached["model"]
                self.metrics = cached["metrics"]
                self._is_trained = True
                return self.metrics
            except Exception:
                pass

        # 데이터 로드
        if data_path is None:
            data_path = ML_DATA_DIR / "mold_training_data.csv"

        if not Path(data_path).exists():
            raise FileNotFoundError(
                f"학습 데이터 없음: {data_path}\n"
                "python -m scripts.generate_mold_ml_data 를 먼저 실행하세요."
            )

        df = pd.read_csv(data_path)

        X = df[FEATURE_COLS].values
        y = df[TARGET_COL].values

        # Train/Test 분할 (80/20)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42,
        )

        # XGBoost 모델 (또는 폴백)
        if XGBOOST_AVAILABLE:
            self.model = XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=3,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                verbosity=0,
            )
        else:
            self.model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
            )

        self.model.fit(X_train, y_train)

        # 평가
        y_pred = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = r2_score(y_test, y_pred)

        # Feature Importance
        importances = self.model.feature_importances_
        fi_dict = {FEATURE_COLS[i]: float(importances[i]) for i in range(len(FEATURE_COLS))}

        self.metrics = ModelMetrics(
            mae=round(mae, 0),
            rmse=round(rmse, 0),
            r2=round(r2, 4),
            train_size=len(X_train),
            test_size=len(X_test),
            feature_importance=fi_dict,
        )

        self._is_trained = True

        # 캐시 저장
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"model": self.model, "metrics": self.metrics}, f)

        return self.metrics

    def predict_mold(
        self,
        mold_data: Dict,
        daily_shots: int = DAILY_SHOTS_ESTIMATE,
    ) -> MoldPredictionResult:
        """
        개별 금형 잔여수명 예측

        Args:
            mold_data: 금형 정보 dict (FEATURE_COLS의 키를 포함)
            daily_shots: 일일 평균 타수 (교체일 계산용)
        """
        if not self._is_trained:
            self.train()

        # 특성 벡터 구성
        features = np.array([[mold_data.get(col, 0) for col in FEATURE_COLS]])

        # 예측
        predicted_remaining = max(0, int(self.model.predict(features)[0]))

        current_shots = int(mold_data.get("current_shots", 0))
        designed_life = int(mold_data.get("designed_life", 100000))
        predicted_failure = current_shots + predicted_remaining

        # 교체일 계산
        if daily_shots > 0 and predicted_remaining > 0:
            days = predicted_remaining // daily_shots
            replacement_date = (date.today() + timedelta(days=days)).isoformat()
        else:
            replacement_date = date.today().isoformat()

        # 신뢰구간 (MAE 기반 간이 추정)
        mae = self.metrics.mae if self.metrics else 5000
        ci_lower = max(0, predicted_remaining - int(mae * 1.96))
        ci_upper = predicted_remaining + int(mae * 1.96)

        # 리스크 레벨
        usage = mold_data.get("usage_ratio", 0)
        defect = mold_data.get("current_defect_rate", 0)
        if predicted_remaining < 5000 or usage > 0.95 or defect > 1.0:
            risk = "critical"
        elif predicted_remaining < 20000 or usage > 0.80 or defect > 0.5:
            risk = "warning"
        else:
            risk = "normal"

        # 수명 영향 요인 Top-5
        top_factors = self._get_top_factors(features[0])

        return MoldPredictionResult(
            mold_id=str(mold_data.get("mold_id", mold_data.get("id", ""))),
            mold_name=mold_data.get("mold_name", mold_data.get("name", "")),
            current_shots=current_shots,
            designed_life=designed_life,
            predicted_remaining=predicted_remaining,
            predicted_failure_shots=predicted_failure,
            predicted_replacement_date=replacement_date,
            confidence_interval=(ci_lower, ci_upper),
            risk_level=risk,
            top_factors=top_factors,
            current_defect_rate=float(mold_data.get("current_defect_rate", 0)),
            usage_ratio=float(mold_data.get("usage_ratio", 0)),
        )

    def predict_all_molds(self) -> List[MoldPredictionResult]:
        """기존 25건 전체 금형 예측"""
        if not self._is_trained:
            self.train()

        molds = self._load_current_molds()
        results = []

        for mold in molds:
            # 기존 DB 필드를 특성으로 변환
            designed_life = mold.get("designed_life", mold.get("max_shots", 100000))
            current_shots = mold.get("current_shots", mold.get("shot_count", 0))
            product = mold.get("product", mold.get("product_type", "default"))
            material = mold.get("material", "SKD11")

            from scripts.generate_mold_ml_data import MATERIAL_LIFE_FACTOR, _get_load_factor

            mold_features = {
                "mold_id": mold.get("id", mold.get("mold_id", "")),
                "mold_name": mold.get("name", mold.get("mold_name", "")),
                "usage_ratio": current_shots / designed_life if designed_life > 0 else 0,
                "current_defect_rate": mold.get("defect_rate", mold.get("current_defect_rate", 0.1)),
                "recent_defect_avg": mold.get("defect_rate", 0.1),
                "defect_slope": 0.001,  # 기본값 (이력 부족)
                "maintenance_count": mold.get("maintenance_count", 3),
                "material_factor": MATERIAL_LIFE_FACTOR.get(material, 1.0),
                "load_factor": _get_load_factor(product),
                "spc_anomaly_rate": 5.0,  # 기본값 (아이디어 ① 연계 시 실제값 대체)
                "designed_life": designed_life,
                "current_shots": current_shots,
            }

            pred = self.predict_mold(mold_features)
            results.append(pred)

        # 리스크 순 정렬
        risk_order = {"critical": 0, "warning": 1, "normal": 2}
        results.sort(key=lambda r: (risk_order.get(r.risk_level, 3), -r.usage_ratio))

        return results

    def _get_top_factors(self, features: np.ndarray, top_k: int = 5) -> List[Dict]:
        """개별 예측의 수명 영향 요인 분석 (Feature Importance × 특성값)"""
        if self.metrics is None:
            return []

        fi = self.metrics.feature_importance
        factors = []
        for i, col in enumerate(FEATURE_COLS):
            importance = fi.get(col, 0)
            value = float(features[i])
            label = FEATURE_LABELS_KR.get(col, col)

            factors.append({
                "feature": col,
                "label": label,
                "importance": round(importance * 100, 1),
                "value": round(value, 4),
            })

        factors.sort(key=lambda x: x["importance"], reverse=True)
        return factors[:top_k]

    def _load_current_molds(self) -> List[Dict]:
        """기존 mold_lifecycle.db에서 현재 금형 로드"""
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

    def predict(self, mold_id: str) -> Optional[Dict]:
        """
        UI 호환 메서드: mold_id로 예측 후 dict 반환.
        page_equipment.py에서 mold_predictor.predict(m["mold_id"]) 형태로 호출.
        """
        if not self._is_trained:
            self.train()

        molds = self._load_current_molds()
        mold = next(
            (m for m in molds if m.get("id") == mold_id or m.get("mold_id") == mold_id),
            None,
        )
        if mold is None:
            return None

        # DB 필드 → ML 특성 변환
        designed_life = mold.get("designed_life", mold.get("max_shots", 100000))
        current_shots = mold.get("current_shots", mold.get("shot_count", 0))
        product = mold.get("product", mold.get("product_type", "default"))
        material = mold.get("material", "SKD11")

        try:
            from scripts.generate_mold_ml_data import MATERIAL_LIFE_FACTOR, _get_load_factor
            mat_factor = MATERIAL_LIFE_FACTOR.get(material, 1.0)
            load_factor = _get_load_factor(product)
        except Exception:
            mat_factor = 1.0
            load_factor = 1.0

        mold_features = {
            "mold_id": mold_id,
            "mold_name": mold.get("name", mold.get("mold_name", "")),
            "usage_ratio": current_shots / designed_life if designed_life > 0 else 0,
            "current_defect_rate": mold.get("defect_rate", mold.get("current_defect_rate", 0.1)),
            "recent_defect_avg": mold.get("defect_rate", 0.1),
            "defect_slope": 0.001,
            "maintenance_count": mold.get("maintenance_count", 3),
            "material_factor": mat_factor,
            "load_factor": load_factor,
            "spc_anomaly_rate": 5.0,
            "designed_life": designed_life,
            "current_shots": current_shots,
        }

        result = self.predict_mold(mold_features)

        return {
            "risk_level": result.risk_level,
            "predicted_remaining_life": result.predicted_remaining,
            "predicted_failure_shots": result.predicted_failure_shots,
            "predicted_replacement_date": result.predicted_replacement_date,
            "confidence_interval": result.confidence_interval,
            "top_features": [f["label"] for f in result.top_factors],
            "usage_ratio": result.usage_ratio,
            "current_defect_rate": result.current_defect_rate,
        }

    def get_feature_importance_chart(self):
        """UI 호환 메서드: Feature Importance 차트 반환"""
        if self.metrics is None:
            return None
        return build_feature_importance_chart(self.metrics)


# ──────────────────────────────────────────────
# Plotly 시각화
# ──────────────────────────────────────────────

def build_mold_prediction_chart(results: List[MoldPredictionResult]) -> go.Figure:
    """전체 금형 잔여수명 예측 수평 막대 차트"""
    fig = go.Figure()

    names = [f"{r.mold_name}" for r in results]
    remaining_pct = [
        r.predicted_remaining / r.designed_life * 100 if r.designed_life > 0 else 0
        for r in results
    ]
    colors = [
        "#D32F2F" if r.risk_level == "critical"
        else "#F57C00" if r.risk_level == "warning"
        else "#388E3C"
        for r in results
    ]

    fig.add_trace(go.Bar(
        x=remaining_pct, y=names, orientation="h",
        marker_color=colors,
        text=[
            f"잔여 {r.predicted_remaining:,}타 | 교체 {r.predicted_replacement_date}"
            for r in results
        ],
        textposition="auto",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "잔여수명: %{x:.1f}%<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="XGBoost 금형 잔여수명 예측",
        xaxis_title="잔여수명 (%)",
        height=max(300, len(results) * 35),
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(autorange="reversed"),
    )

    return fig


def build_feature_importance_chart(metrics: ModelMetrics) -> go.Figure:
    """Feature Importance 막대 차트"""
    fi = metrics.feature_importance
    sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)

    labels = [FEATURE_LABELS_KR.get(k, k) for k, _ in sorted_fi]
    values = [v * 100 for _, v in sorted_fi]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color="#1976D2",
        text=[f"{v:.1f}%" for v in values],
        textposition="auto",
    ))

    fig.update_layout(
        title="수명 예측 영향 요인 (Feature Importance)",
        xaxis_title="중요도 (%)",
        height=320,
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(autorange="reversed"),
    )

    return fig


def build_bathtub_curve_chart(mold_data: Dict, prediction: MoldPredictionResult) -> go.Figure:
    """개별 금형의 바스텁 커브 + 현재 위치 + 예측 구간"""
    from scripts.generate_mold_ml_data import bathtub_defect_curve, MATERIAL_LIFE_FACTOR, _get_load_factor

    designed_life = mold_data.get("designed_life", 100000)
    material = mold_data.get("material", "SKD11")
    product = mold_data.get("product", "default")

    mat_factor = MATERIAL_LIFE_FACTOR.get(material, 1.0)
    load_factor = _get_load_factor(product)

    # 전체 수명 구간 커브
    shots_range = np.linspace(0, int(designed_life * 1.2), 200)
    defect_curve = bathtub_defect_curve(
        shots_range, designed_life, mat_factor, load_factor,
        maintenance_quality=1.0, noise_std=0.01, seed=42,
    )

    fig = go.Figure()

    # 바스텁 커브
    fig.add_trace(go.Scatter(
        x=shots_range, y=defect_curve,
        mode="lines", line=dict(width=2, color="#1976D2"),
        name="불량률 곡선 (이론)",
        fill="tozeroy", fillcolor="rgba(25,118,210,0.1)",
    ))

    # 불량률 임계선
    fig.add_hline(y=1.0, line_dash="dash", line_color="red",
                  annotation_text="불량률 1% 임계치")
    fig.add_hline(y=0.5, line_dash="dot", line_color="orange",
                  annotation_text="경고 0.5%")

    # 현재 위치
    fig.add_trace(go.Scatter(
        x=[prediction.current_shots],
        y=[prediction.current_defect_rate],
        mode="markers", marker=dict(size=15, color="#D32F2F", symbol="star"),
        name=f"현재 위치 ({prediction.current_shots:,}타)",
    ))

    # 예측 고장 시점
    fig.add_vline(x=prediction.predicted_failure_shots,
                  line_dash="dash", line_color="#F57C00",
                  annotation_text=f"예측 교체 시점: {prediction.predicted_failure_shots:,}타")

    # 신뢰구간 영역
    ci_low = prediction.current_shots + prediction.confidence_interval[0]
    ci_high = prediction.current_shots + prediction.confidence_interval[1]
    fig.add_vrect(x0=ci_low, x1=ci_high,
                  fillcolor="rgba(255,152,0,0.1)", line_width=0,
                  annotation_text="95% 신뢰구간")

    fig.update_layout(
        title=f"바스텁 커브: {prediction.mold_name}",
        xaxis_title="누적 타수",
        yaxis_title="불량률 (%)",
        height=350,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig


# ──────────────────────────────────────────────
# 싱글턴 인스턴스
# ──────────────────────────────────────────────

_predictor_instance: Optional[MoldLifeXGBPredictor] = None

def get_mold_predictor() -> MoldLifeXGBPredictor:
    """싱글턴 예측기 인스턴스"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = MoldLifeXGBPredictor()
        _predictor_instance.train()
    return _predictor_instance
