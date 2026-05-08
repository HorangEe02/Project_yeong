"""
마르코프 체인 기반 설비 고장 예측 엔진
- 이벤트 시퀀스에서 전이 확률 행렬 학습
- "현재 에러코드 → 다음 예상 에러코드 Top-N" 예측
- 다단계 전이 (2~3스텝 앞) 예측
- 연쇄 고장 경로 시각화
"""

import numpy as np
import json
import pickle
import sqlite3
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

import plotly.graph_objects as go


DATA_DIR = Path("data/markov_ml")
MODEL_PATH = DATA_DIR / "markov_model.pkl"
ERROR_CODES_DB = "data/equipment/error_codes.db"


@dataclass
class FailurePrediction:
    """다음 예상 에러코드"""
    code: str
    category: str
    equipment_type: str
    probability: float          # 전이 확률 (%)
    expected_delay_hours: float  # 예상 발생 시간 (시간)
    description: str            # 에러코드 설명
    recommended_action: str     # 예방 조치


@dataclass
class CascadeChain:
    """연쇄 고장 경로"""
    steps: List[FailurePrediction]
    total_probability: float    # 전체 경로 확률 (곱)
    total_hours: float          # 전체 예상 시간


@dataclass
class MarkovAnalysis:
    """마르코프 분석 결과"""
    current_code: str
    current_category: str
    next_predictions: List[FailurePrediction]      # 1스텝 예측
    cascade_chains: List[CascadeChain]              # 2~3스텝 연쇄 경로
    risk_level: str             # "critical" / "warning" / "normal"
    prevention_message: str


class MarkovFailurePredictor:
    """마르코프 체인 설비 고장 예측기"""

    def __init__(self):
        self.transition_matrix: Dict[str, Dict[str, float]] = {}  # cat → {next_cat: prob}
        self.delay_matrix: Dict[str, Dict[str, float]] = {}       # cat → {next_cat: avg_hours}
        self.category_codes: Dict[str, List[str]] = {}            # cat → [codes]
        self.code_info: Dict[str, Dict] = {}                      # code → {description, action, ...}
        self._is_trained = False

    def train(self, sequences_path: str = None, force: bool = False) -> Dict:
        """전이 확률 행렬 학습"""

        # 캐시 로드
        if not force and MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    cached = pickle.load(f)
                self.transition_matrix = cached["transition_matrix"]
                self.delay_matrix = cached["delay_matrix"]
                self.category_codes = cached["category_codes"]
                self.code_info = cached.get("code_info", {})
                self._is_trained = True
                return self._get_stats()
            except Exception:
                pass

        # 시퀀스 로드
        if sequences_path is None:
            sequences_path = str(DATA_DIR / "event_sequences.json")

        if not Path(sequences_path).exists():
            raise FileNotFoundError(
                f"시퀀스 데이터 없음: {sequences_path}\n"
                "python -c \"from features.equipment.error_causality import *; "
                "save_sequences(generate_event_sequences())\" 를 먼저 실행하세요."
            )

        with open(sequences_path, "r", encoding="utf-8") as f:
            sequences = json.load(f)

        # 전이 카운트 집계
        transition_counts = defaultdict(lambda: defaultdict(int))
        delay_sums = defaultdict(lambda: defaultdict(list))
        cat_codes = defaultdict(set)

        for seq in sequences:
            for i in range(len(seq) - 1):
                from_cat = seq[i]["category"]
                to_cat = seq[i + 1]["category"]
                from_code = seq[i]["code"]
                to_code = seq[i + 1]["code"]

                transition_counts[from_cat][to_cat] += 1
                cat_codes[from_cat].add(from_code)
                cat_codes[to_cat].add(to_code)

                # 지연 시간 계산
                try:
                    from datetime import datetime
                    t1 = datetime.fromisoformat(seq[i]["timestamp"])
                    t2 = datetime.fromisoformat(seq[i + 1]["timestamp"])
                    delay = (t2 - t1).total_seconds() / 3600
                    delay_sums[from_cat][to_cat].append(delay)
                except (ValueError, KeyError):
                    pass

        # 카운트 → 확률 정규화
        self.transition_matrix = {}
        for from_cat, targets in transition_counts.items():
            total = sum(targets.values())
            self.transition_matrix[from_cat] = {
                to_cat: round(count / total, 4)
                for to_cat, count in sorted(targets.items(), key=lambda x: x[1], reverse=True)
            }

        # 평균 지연 시간
        self.delay_matrix = {}
        for from_cat, targets in delay_sums.items():
            self.delay_matrix[from_cat] = {
                to_cat: round(np.mean(delays), 1)
                for to_cat, delays in targets.items()
            }

        self.category_codes = {k: list(v) for k, v in cat_codes.items()}

        # 에러코드 상세 정보 로드
        self._load_code_info()

        self._is_trained = True

        # 캐시 저장
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({
                "transition_matrix": self.transition_matrix,
                "delay_matrix": self.delay_matrix,
                "category_codes": self.category_codes,
                "code_info": self.code_info,
            }, f)

        return self._get_stats()

    def predict_next(
        self,
        current_code: str,
        current_category: str = None,
        top_k: int = 5,
    ) -> MarkovAnalysis:
        """다음 예상 에러코드 예측"""
        if not self._is_trained:
            self.train()

        # 카테고리 추론
        if current_category is None:
            current_category = self._infer_category(current_code)

        # 1스텝 전이 확률
        transitions = self.transition_matrix.get(current_category, {})

        next_predictions = []
        for to_cat, prob in list(transitions.items())[:top_k]:
            codes = self.category_codes.get(to_cat, [f"{to_cat}-001"])
            representative_code = codes[0] if codes else f"{to_cat}-001"
            delay = self.delay_matrix.get(current_category, {}).get(to_cat, 6.0)

            info = self.code_info.get(representative_code, {})

            next_predictions.append(FailurePrediction(
                code=representative_code,
                category=to_cat,
                equipment_type=info.get("equipment_type", self._infer_equipment(to_cat)),
                probability=round(prob * 100, 1),
                expected_delay_hours=delay,
                description=info.get("description", f"{to_cat} 카테고리 에러"),
                recommended_action=info.get("action", f"{to_cat} 관련 장비 사전 점검 실시"),
            ))

        # 2~3스텝 연쇄 경로 (Top-3 경로)
        cascade_chains = self._predict_cascade(current_category, max_depth=3, top_k=3)

        # 리스크 판정
        max_prob = max((p.probability for p in next_predictions), default=0)
        if max_prob >= 35:
            risk = "critical"
            msg = f"높은 연쇄 고장 위험! {next_predictions[0].category} 관련 장비 즉시 점검 필요"
        elif max_prob >= 20:
            risk = "warning"
            msg = f"연쇄 고장 주의. {next_predictions[0].category} 관련 예방 점검 권장"
        else:
            risk = "normal"
            msg = "연쇄 고장 위험 낮음. 정상 모니터링 유지"

        return MarkovAnalysis(
            current_code=current_code,
            current_category=current_category,
            next_predictions=next_predictions,
            cascade_chains=cascade_chains,
            risk_level=risk,
            prevention_message=msg,
        )

    def _predict_cascade(
        self,
        start_cat: str,
        max_depth: int = 3,
        top_k: int = 3,
    ) -> List[CascadeChain]:
        """다단계 연쇄 고장 경로 탐색 (DFS)"""
        paths = []
        self._dfs_cascade(start_cat, [], 1.0, 0.0, max_depth, paths)

        # 확률 순 정렬
        paths.sort(key=lambda p: p.total_probability, reverse=True)
        return paths[:top_k]

    def _dfs_cascade(self, cat, current_path, current_prob, current_hours, remaining, all_paths):
        """DFS로 연쇄 경로 탐색"""
        if remaining <= 0 or current_prob < 0.01:
            if len(current_path) >= 2:
                all_paths.append(CascadeChain(
                    steps=list(current_path),
                    total_probability=round(current_prob * 100, 2),
                    total_hours=round(current_hours, 1),
                ))
            return

        transitions = self.transition_matrix.get(cat, {})
        for to_cat, prob in list(transitions.items())[:3]:  # 상위 3개만 탐색
            delay = self.delay_matrix.get(cat, {}).get(to_cat, 6.0)
            codes = self.category_codes.get(to_cat, [f"{to_cat}-001"])
            info = self.code_info.get(codes[0], {})

            step = FailurePrediction(
                code=codes[0],
                category=to_cat,
                equipment_type=info.get("equipment_type", self._infer_equipment(to_cat)),
                probability=round(prob * 100, 1),
                expected_delay_hours=delay,
                description=info.get("description", f"{to_cat} 에러"),
                recommended_action=info.get("action", "점검 필요"),
            )

            current_path.append(step)
            self._dfs_cascade(
                to_cat, current_path,
                current_prob * prob,
                current_hours + delay,
                remaining - 1,
                all_paths,
            )
            current_path.pop()

    def _load_code_info(self):
        """error_codes.db에서 에러코드 상세 정보 로드"""
        db_path = Path(ERROR_CODES_DB)
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT * FROM error_codes"):
                r = dict(row)
                code = r.get("code", "")
                self.code_info[code] = {
                    "equipment_type": r.get("equipment_type", ""),
                    "category": r.get("category", ""),
                    "description": r.get("description", ""),
                    "cause": r.get("cause", r.get("possible_cause", "")),
                    "action": r.get("action", r.get("recommended_action", "")),
                    "severity": r.get("severity", ""),
                }
            conn.close()
        except Exception:
            pass

    def _infer_category(self, code: str) -> str:
        """에러코드에서 카테고리 추론"""
        info = self.code_info.get(code, {})
        if info.get("category"):
            return info["category"]
        # 코드 접두어에서 추론 (HYD-001 → HYD)
        parts = code.split("-")
        if len(parts) >= 2:
            prefix = parts[0]
            if prefix in self.transition_matrix:
                return prefix
            # COM-E-001 같은 경우
            if len(parts) >= 3:
                return f"{parts[0]}-{parts[1]}"
        return code

    def _infer_equipment(self, category: str) -> str:
        """카테고리에서 장비유형 추론"""
        from features.equipment.error_causality import _infer_equipment_type
        return _infer_equipment_type(category)

    def _get_stats(self) -> Dict:
        """모델 통계"""
        return {
            "categories": len(self.transition_matrix),
            "total_transitions": sum(
                len(targets) for targets in self.transition_matrix.values()
            ),
            "unique_codes": len(self.code_info),
            "is_trained": self._is_trained,
        }


# ──────────────────────────────────────────────
# Plotly 시각화
# ──────────────────────────────────────────────

def build_cascade_chart(analysis: MarkovAnalysis) -> go.Figure:
    """연쇄 고장 예측 Sankey 다이어그램"""
    labels = [f"현재: {analysis.current_code}"]
    sources, targets, values, colors = [], [], [], []
    link_labels = []

    # 1스텝 노드 추가
    for i, pred in enumerate(analysis.next_predictions[:5]):
        label = f"{pred.code}\n({pred.category})\n{pred.probability}%"
        labels.append(label)
        sources.append(0)
        targets.append(i + 1)
        values.append(pred.probability)
        link_labels.append(f"{pred.expected_delay_hours:.0f}h 후")

        if pred.probability >= 30:
            colors.append("rgba(211,47,47,0.6)")
        elif pred.probability >= 15:
            colors.append("rgba(245,124,0,0.6)")
        else:
            colors.append("rgba(25,118,210,0.4)")

    fig = go.Figure(go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            label=labels,
            color=["#1976D2"] + [
                "#D32F2F" if p.probability >= 30
                else "#F57C00" if p.probability >= 15
                else "#388E3C"
                for p in analysis.next_predictions[:5]
            ],
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=colors,
            label=link_labels,
        ),
    ))

    fig.update_layout(
        title=f"연쇄 고장 예측: {analysis.current_code} ({analysis.current_category})",
        height=350,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig


def build_transition_heatmap(predictor: MarkovFailurePredictor) -> go.Figure:
    """전이 확률 히트맵"""
    cats = sorted(predictor.transition_matrix.keys())

    z = []
    for from_cat in cats:
        row = []
        for to_cat in cats:
            prob = predictor.transition_matrix.get(from_cat, {}).get(to_cat, 0)
            row.append(round(prob * 100, 1))
        z.append(row)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=cats,
        y=cats,
        text=[[f"{v}%" if v > 0 else "" for v in row] for row in z],
        texttemplate="%{text}",
        colorscale="YlOrRd",
        hovertemplate="From: %{y}<br>To: %{x}<br>확률: %{z}%<extra></extra>",
    ))

    fig.update_layout(
        title="에러코드 카테고리 간 전이 확률 행렬",
        xaxis_title="다음 카테고리",
        yaxis_title="현재 카테고리",
        height=450,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig


# ──────────────────────────────────────────────
# 싱글턴
# ──────────────────────────────────────────────

_predictor_instance: Optional[MarkovFailurePredictor] = None

def get_markov_predictor() -> MarkovFailurePredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = MarkovFailurePredictor()
        _predictor_instance.train()
    return _predictor_instance
