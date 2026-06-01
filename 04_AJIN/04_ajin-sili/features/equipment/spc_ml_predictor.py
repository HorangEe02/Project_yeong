"""
SPC ML 이상 예측 엔진
- Isolation Forest: 개별 측정값의 이상 확률(%) 산출
- 이동 윈도우 Cpk: 슬라이딩 윈도우로 Cpk 변화 추이 계산
- 선형 회귀 예측: 향후 N포인트 Cpk 추이 예측
- 조기 경고: Cpk 하락 추세 감지 시 알림
"""

import numpy as np
import pandas as pd
import pickle
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

import plotly.graph_objects as go
from plotly.subplots import make_subplots


ML_DATA_DIR = Path("data/spc_ml")
MODEL_CACHE_DIR = Path("data/spc_ml/models")

# IATF 16949 Cpk 기준
CPK_THRESHOLDS = {
    "A": 1.67,   # 우수
    "B": 1.33,   # 양산 적합
    "C": 1.00,   # 개선 필요
    "D": 0.0,    # 부적합
}


@dataclass
class AnomalyResult:
    """개별 측정값 이상 탐지 결과"""
    index: int
    value: float
    anomaly_score: float      # Isolation Forest 점수 (-1 ~ 0, 낮을수록 이상)
    anomaly_probability: float # 이상 확률 (0~100%)
    is_anomaly: bool
    anomaly_type_predicted: str  # "spike" / "shift" / "drift" / "variance" / "normal"


@dataclass
class CpkPrediction:
    """Cpk 트렌드 예측 결과"""
    current_cpk: float
    predicted_cpk_10: float    # 10포인트 후 예측 Cpk
    predicted_cpk_30: float    # 30포인트 후 예측 Cpk
    predicted_cpk_50: float    # 50포인트 후 예측 Cpk
    trend: str                 # "improving" / "stable" / "declining" / "critical_decline"
    slope: float               # Cpk 변화 기울기 (포인트당)
    points_to_threshold: Optional[int]  # Cpk 1.33 도달까지 남은 포인트 수
    warning_message: str


@dataclass
class SPCMLAnalysis:
    """SPC ML 분석 종합 결과"""
    process_name: str
    total_points: int
    anomaly_count: int
    anomaly_rate: float
    anomaly_details: List[AnomalyResult]
    cpk_prediction: CpkPrediction
    risk_level: str            # "critical" / "warning" / "normal"


# ──────────────────────────────────────────────
# 1. Isolation Forest 이상 탐지
# ──────────────────────────────────────────────

class SPCAnomalyDetector:
    """Isolation Forest 기반 SPC 이상 탐지기"""

    def __init__(self, contamination: float = 0.1):
        """
        Args:
            contamination: 예상 이상치 비율 (0.05~0.15)
        """
        self.contamination = contamination
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self._is_fitted = False

    def fit(self, values: np.ndarray):
        """정상 패턴 학습"""
        # 특성 엔지니어링: 원시값 + 차분 + 이동평균 편차
        features = self._extract_features(values)

        self.scaler = StandardScaler()
        features_scaled = self.scaler.fit_transform(features)

        self.model = IsolationForest(
            n_estimators=200,
            contamination=self.contamination,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(features_scaled)
        self._is_fitted = True

    def predict(self, values: np.ndarray) -> List[AnomalyResult]:
        """이상 탐지 실행"""
        if not self._is_fitted:
            raise RuntimeError("모델이 학습되지 않았습니다. fit()을 먼저 호출하세요.")

        features = self._extract_features(values)
        features_scaled = self.scaler.transform(features)

        # Isolation Forest 점수 (-1에 가까울수록 이상)
        scores = self.model.decision_function(features_scaled)
        predictions = self.model.predict(features_scaled)  # 1=정상, -1=이상

        # 점수를 확률로 변환 (min-max 스케일링 → 0~100%)
        min_score, max_score = scores.min(), scores.max()
        score_range = max_score - min_score if max_score > min_score else 1.0
        probabilities = ((max_score - scores) / score_range) * 100

        results = []
        for i in range(len(values)):
            is_anom = predictions[i] == -1
            anom_type = self._classify_anomaly_type(values, i) if is_anom else "normal"

            results.append(AnomalyResult(
                index=i,
                value=float(values[i]),
                anomaly_score=float(scores[i]),
                anomaly_probability=float(np.clip(probabilities[i], 0, 100)),
                is_anomaly=is_anom,
                anomaly_type_predicted=anom_type,
            ))

        return results

    def _extract_features(self, values: np.ndarray) -> np.ndarray:
        """특성 엔지니어링 (5차원)"""
        n = len(values)
        features = np.zeros((n, 5))

        # F1: 원시값
        features[:, 0] = values

        # F2: 1차 차분 (변화량)
        diff1 = np.diff(values, prepend=values[0])
        features[:, 1] = diff1

        # F3: 이동평균(10) 대비 편차
        window = min(10, n)
        ma = pd.Series(values).rolling(window=window, min_periods=1).mean().values
        features[:, 2] = values - ma

        # F4: 이동표준편차(10)
        mstd = pd.Series(values).rolling(window=window, min_periods=1).std().fillna(0).values
        features[:, 3] = mstd

        # F5: Z-score (전체 기준)
        mean_val = np.mean(values)
        std_val = np.std(values) if np.std(values) > 0 else 1.0
        features[:, 4] = (values - mean_val) / std_val

        return features

    def _classify_anomaly_type(self, values: np.ndarray, idx: int) -> str:
        """이상 유형 추정 (규칙 기반)"""
        n = len(values)
        val = values[idx]
        mean_all = np.mean(values)
        std_all = np.std(values)

        if std_all == 0:
            return "spike"

        z_score = abs(val - mean_all) / std_all

        # Spike: Z-score > 4
        if z_score > 4:
            return "spike"

        # Shift: 전후 10포인트 평균 차이 > 2σ
        window = 10
        start = max(0, idx - window)
        end = min(n, idx + window)
        local_mean = np.mean(values[start:end])
        if abs(local_mean - mean_all) > 2 * std_all:
            return "shift"

        # Drift: 전후 구간 기울기 > 임계치
        if idx >= 5 and idx < n - 5:
            before = np.mean(values[idx-5:idx])
            after = np.mean(values[idx:idx+5])
            if abs(after - before) > 1.5 * std_all:
                return "drift"

        # Variance: 로컬 분산이 전체 대비 2배 이상
        local_std = np.std(values[start:end])
        if local_std > 2 * std_all:
            return "variance"

        return "shift"  # 기본값

    def save(self, path: str):
        """모델 저장"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)

    def load(self, path: str) -> bool:
        """모델 로드"""
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._is_fitted = True
            return True
        except Exception:
            return False


# ──────────────────────────────────────────────
# 2. 이동 윈도우 Cpk 트렌드 + 예측
# ──────────────────────────────────────────────

def calculate_rolling_cpk(
    values: np.ndarray,
    usl: float,
    lsl: float,
    window: int = 30,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    이동 윈도우 Cpk 계산

    Returns:
        (cpk_values, valid_indices) — 윈도우 충족 구간만
    """
    n = len(values)
    cpk_list = []
    idx_list = []

    for i in range(window - 1, n):
        window_data = values[i - window + 1:i + 1]
        mean = np.mean(window_data)
        std = np.std(window_data, ddof=1)

        if std > 0:
            cpu = (usl - mean) / (3 * std)
            cpl = (mean - lsl) / (3 * std)
            cpk = min(cpu, cpl)
        else:
            cpk = 99.0  # 분산 0이면 무한대

        cpk_list.append(cpk)
        idx_list.append(i)

    return np.array(cpk_list), np.array(idx_list)


def predict_cpk_trend(
    cpk_values: np.ndarray,
    forecast_points: List[int] = None,
) -> CpkPrediction:
    """
    Cpk 트렌드 선형 회귀 예측

    Args:
        cpk_values: 이동 윈도우 Cpk 시퀀스
        forecast_points: 예측할 미래 포인트 수 리스트 [10, 30, 50]
    """
    if forecast_points is None:
        forecast_points = [10, 30, 50]

    n = len(cpk_values)
    if n < 5:
        return CpkPrediction(
            current_cpk=float(cpk_values[-1]) if n > 0 else 0,
            predicted_cpk_10=0, predicted_cpk_30=0, predicted_cpk_50=0,
            trend="insufficient_data", slope=0,
            points_to_threshold=None,
            warning_message="분석에 필요한 데이터가 부족합니다.",
        )

    # 최근 50% 구간에서 트렌드 추출 (전체를 쓰면 초기 불안정 구간 영향)
    recent_n = max(10, n // 2)
    recent_cpk = cpk_values[-recent_n:]
    X = np.arange(recent_n).reshape(-1, 1)

    reg = LinearRegression()
    reg.fit(X, recent_cpk)
    slope = float(reg.coef_[0])
    current_cpk = float(cpk_values[-1])

    # 미래 예측
    predictions = {}
    for fp in forecast_points:
        future_x = np.array([[recent_n + fp]])
        pred = float(reg.predict(future_x)[0])
        predictions[fp] = max(0, pred)  # 음수 방지

    # 트렌드 판정
    if slope < -0.005:
        trend = "critical_decline"
    elif slope < -0.001:
        trend = "declining"
    elif slope > 0.001:
        trend = "improving"
    else:
        trend = "stable"

    # Cpk 1.33 도달까지 남은 포인트 수
    threshold = CPK_THRESHOLDS["B"]  # 1.33
    if current_cpk > threshold and slope < 0:
        points_to_threshold = int((current_cpk - threshold) / abs(slope))
    else:
        points_to_threshold = None

    # 경고 메시지
    if trend == "critical_decline":
        warning = f"Cpk 급격 하락 추세! 포인트당 {abs(slope):.4f} 감소. " \
                  f"{'약 ' + str(points_to_threshold) + '포인트 후 기준 미달 예상' if points_to_threshold else '즉시 공정 점검 필요'}"
    elif trend == "declining":
        warning = f"Cpk 완만 하락 추세 (포인트당 {abs(slope):.4f} 감소). 공정 상태 모니터링 강화 필요"
    elif trend == "improving":
        warning = f"Cpk 개선 추세 (포인트당 {slope:.4f} 증가). 현재 공정 조건 유지 권장"
    else:
        warning = "Cpk 안정적. 정상 공정 상태 유지 중"

    return CpkPrediction(
        current_cpk=current_cpk,
        predicted_cpk_10=predictions.get(10, 0),
        predicted_cpk_30=predictions.get(30, 0),
        predicted_cpk_50=predictions.get(50, 0),
        trend=trend,
        slope=slope,
        points_to_threshold=points_to_threshold,
        warning_message=warning,
    )


# ──────────────────────────────────────────────
# 3. 종합 분석 + Plotly 시각화
# ──────────────────────────────────────────────

def run_spc_ml_analysis(
    process_id: str,
    values: np.ndarray = None,
    usl: float = None,
    lsl: float = None,
    contamination: float = 0.1,
) -> Optional[SPCMLAnalysis]:
    """
    SPC ML 종합 분석 실행

    Args:
        process_id: 공정 ID (예: "ewp_housing_bore")
        values: 측정값 배열 (None이면 합성 데이터 로드)
        usl/lsl: 규격 상/하한 (None이면 합성 데이터에서 로드)
        contamination: Isolation Forest 이상치 비율
    """
    from scripts.generate_spc_ml_data import PROCESS_SPECS

    spec = PROCESS_SPECS.get(process_id)
    if spec is None:
        return None

    # 데이터 로드
    if values is None:
        csv_path = ML_DATA_DIR / f"{process_id}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            values = df["value"].values
            usl = df["usl"].iloc[0]
            lsl = df["lsl"].iloc[0]
        else:
            return None

    if usl is None:
        usl = spec["usl"]
    if lsl is None:
        lsl = spec["lsl"]

    # 1) Isolation Forest 이상 탐지
    model_path = str(MODEL_CACHE_DIR / f"iforest_{process_id}.pkl")
    detector = SPCAnomalyDetector(contamination=contamination)

    if not detector.load(model_path):
        detector.fit(values)
        detector.save(model_path)

    anomaly_results = detector.predict(values)
    anomaly_count = sum(1 for r in anomaly_results if r.is_anomaly)

    # 2) 이동 윈도우 Cpk + 예측
    cpk_values, cpk_indices = calculate_rolling_cpk(values, usl, lsl, window=30)
    cpk_pred = predict_cpk_trend(cpk_values)

    # 3) 리스크 레벨
    if cpk_pred.trend == "critical_decline" or cpk_pred.current_cpk < 1.0:
        risk = "critical"
    elif cpk_pred.trend == "declining" or cpk_pred.current_cpk < 1.33:
        risk = "warning"
    else:
        risk = "normal"

    return SPCMLAnalysis(
        process_name=spec["name"],
        total_points=len(values),
        anomaly_count=anomaly_count,
        anomaly_rate=round(anomaly_count / len(values) * 100, 1),
        anomaly_details=anomaly_results,
        cpk_prediction=cpk_pred,
        risk_level=risk,
    )


def build_spc_ml_chart(
    values: np.ndarray,
    analysis: SPCMLAnalysis,
    usl: float,
    lsl: float,
) -> go.Figure:
    """SPC ML 분석 결과 Plotly 차트 (2단 구성)"""

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("측정값 + 이상 탐지", "이동 윈도우 Cpk 트렌드 + 예측"),
        row_heights=[0.55, 0.45],
        vertical_spacing=0.12,
    )

    n = len(values)
    x = list(range(1, n + 1))

    # ── 상단: 측정값 + 이상 탐지 ──
    mean_val = float(np.mean(values))
    std_val = float(np.std(values))

    # 규격 한계선
    fig.add_hline(y=usl, line_dash="dash", line_color="red", row=1, col=1,
                  annotation_text=f"USL={usl}")
    fig.add_hline(y=lsl, line_dash="dash", line_color="red", row=1, col=1,
                  annotation_text=f"LSL={lsl}")
    fig.add_hline(y=mean_val, line_dash="solid", line_color="green", row=1, col=1)

    # 정상 포인트
    normal_idx = [r.index for r in analysis.anomaly_details if not r.is_anomaly]
    normal_vals = [values[i] for i in normal_idx]
    fig.add_trace(go.Scatter(
        x=[i+1 for i in normal_idx], y=normal_vals,
        mode="markers", marker=dict(size=3, color="#1976D2"),
        name="정상", showlegend=True,
    ), row=1, col=1)

    # 이상 포인트 (크기 = 이상 확률 비례)
    anom_results = [r for r in analysis.anomaly_details if r.is_anomaly]
    if anom_results:
        anom_x = [r.index + 1 for r in anom_results]
        anom_y = [r.value for r in anom_results]
        anom_sizes = [max(6, min(15, r.anomaly_probability / 8)) for r in anom_results]
        anom_colors = [
            "#D32F2F" if r.anomaly_probability > 70
            else "#F57C00" if r.anomaly_probability > 40
            else "#FBC02D"
            for r in anom_results
        ]
        anom_texts = [
            f"{r.anomaly_type_predicted}: {r.anomaly_probability:.0f}%"
            for r in anom_results
        ]

        fig.add_trace(go.Scatter(
            x=anom_x, y=anom_y,
            mode="markers",
            marker=dict(size=anom_sizes, color=anom_colors, symbol="x", line=dict(width=1)),
            text=anom_texts,
            hovertemplate="%{text}<br>값: %{y:.4f}<extra></extra>",
            name=f"이상 ({analysis.anomaly_count}건)",
        ), row=1, col=1)

    # ── 하단: Cpk 트렌드 + 예측 ──
    cpk_values, cpk_indices = calculate_rolling_cpk(values, usl, lsl, window=30)

    fig.add_trace(go.Scatter(
        x=[i+1 for i in cpk_indices], y=cpk_values,
        mode="lines", line=dict(width=2, color="#1976D2"),
        name="Cpk (윈도우=30)",
    ), row=2, col=1)

    # Cpk 기준선
    for grade, threshold in CPK_THRESHOLDS.items():
        if threshold > 0:
            color = {"A": "#388E3C", "B": "#F57C00", "C": "#D32F2F"}.get(grade, "gray")
            fig.add_hline(y=threshold, line_dash="dot", line_color=color, row=2, col=1,
                          annotation_text=f"Cpk={threshold} ({grade}등급)")

    # 예측 구간 (점선 연장)
    pred = analysis.cpk_prediction
    if pred.slope != 0 and len(cpk_values) > 0:
        last_idx = int(cpk_indices[-1]) + 1
        future_x = [last_idx + 10, last_idx + 30, last_idx + 50]
        future_cpk = [pred.predicted_cpk_10, pred.predicted_cpk_30, pred.predicted_cpk_50]

        fig.add_trace(go.Scatter(
            x=future_x, y=future_cpk,
            mode="lines+markers",
            line=dict(width=2, color="#F57C00", dash="dash"),
            marker=dict(size=8, symbol="diamond"),
            name="Cpk 예측",
            hovertemplate="예측 Cpk: %{y:.3f}<extra></extra>",
        ), row=2, col=1)

    fig.update_layout(
        height=600,
        title=f"SPC ML 분석: {analysis.process_name}",
        margin=dict(l=0, r=0, t=60, b=0),
    )

    return fig


# ──────────────────────────────────────────────
# 4. UI 호환 래퍼 클래스 (page_equipment.py에서 호출)
# ──────────────────────────────────────────────

class SPCPredictor:
    """page_equipment.py의 UI 코드가 호출하는 래퍼"""

    def __init__(self):
        self._is_trained = False
        self._check_data()

    def _check_data(self):
        """합성 데이터 존�� 여부로 학�� 가능 상태 판단"""
        csv_files = list(ML_DATA_DIR.glob("*.csv"))
        self._is_trained = len(csv_files) > 0

    def analyze(
        self,
        values: list = None,
        process_id: str = "custom",
        usl: float = None,
        lsl: float = None,
    ) -> Optional[Dict]:
        """
        UI에서 호출하는 분석 메서드.
        run_spc_ml_analysis()를 감싸��� 결과를 dict로 반환.
        """
        if values and len(values) < 30:
            return None

        arr = np.array(values) if values else None

        try:
            analysis = run_spc_ml_analysis(
                process_id=process_id,
                values=arr,
                usl=usl,
                lsl=lsl,
            )
        except Exception:
            # process_id가 합성 데이터에 없으면 직접 분석
            if arr is None or usl is None or lsl is None:
                return None
            analysis = self._analyze_custom(arr, usl, lsl)

        if analysis is None:
            if arr is not None and usl is not None and lsl is not None:
                analysis = self._analyze_custom(arr, usl, lsl)
            else:
                return None

        # Cpk ���세 문자열
        cpk_pred = analysis.cpk_prediction
        trend_map = {
            "critical_decline": "급락",
            "declining": "하락",
            "stable": "안정",
            "improving": "개선",
        }
        trend_str = trend_map.get(cpk_pred.trend, cpk_pred.trend) if cpk_pred else "-"

        # 경고 메시지
        warnings = []
        if analysis.risk_level == "critical":
            warnings.append(f"공정 이상 감지: 이상 포인트 {analysis.anomaly_count}건 ({analysis.anomaly_rate}%)")
        if cpk_pred and cpk_pred.current_cpk < 1.33:
            warnings.append(f"Cpk {cpk_pred.current_cpk:.3f} — 양산 기준(1.33) 미달")
        if cpk_pred and cpk_pred.warning_message:
            warnings.append(cpk_pred.warning_message)

        # 차트 생성
        chart = None
        try:
            if arr is not None and usl is not None:
                chart = build_spc_ml_chart(arr, analysis, usl, lsl)
        except Exception:
            pass

        return {
            "anomaly_count": analysis.anomaly_count,
            "anomaly_rate": analysis.anomaly_rate,
            "current_cpk": f"{cpk_pred.current_cpk:.3f}" if cpk_pred else "-",
            "cpk_trend": trend_str,
            "risk_level": analysis.risk_level,
            "warnings": warnings,
            "chart": chart,
        }

    def _analyze_custom(self, values: np.ndarray, usl: float, lsl: float) -> Optional[SPCMLAnalysis]:
        """합성 데이터 없이 커스텀 데이터로 직접 분석"""
        detector = SPCAnomalyDetector(contamination=0.1)
        detector.fit(values)
        anomaly_results = detector.predict(values)
        anomaly_count = sum(1 for r in anomaly_results if r.is_anomaly)

        cpk_values, _ = calculate_rolling_cpk(values, usl, lsl, window=30)
        cpk_pred = predict_cpk_trend(cpk_values)

        if cpk_pred.trend == "critical_decline" or cpk_pred.current_cpk < 1.0:
            risk = "critical"
        elif cpk_pred.trend == "declining" or cpk_pred.current_cpk < 1.33:
            risk = "warning"
        else:
            risk = "normal"

        return SPCMLAnalysis(
            process_name="사용자 입력 데이터",
            total_points=len(values),
            anomaly_count=anomaly_count,
            anomaly_rate=round(anomaly_count / len(values) * 100, 1),
            anomaly_details=anomaly_results,
            cpk_prediction=cpk_pred,
            risk_level=risk,
        )


_spc_predictor_instance: Optional[SPCPredictor] = None


def get_spc_predictor() -> SPCPredictor:
    """싱글턴 SPC 예측기 인스턴스"""
    global _spc_predictor_instance
    if _spc_predictor_instance is None:
        _spc_predictor_instance = SPCPredictor()
    return _spc_predictor_instance
