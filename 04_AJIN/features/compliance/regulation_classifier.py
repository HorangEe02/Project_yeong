"""
규제 리스크 자동 분류 엔진
- TF-IDF + RandomForest로 심각도 분류 (HIGH/MEDIUM/LOW)
- 키워드 매칭으로 관련 부서 자동 매핑
- 영향 시설 자동 추론
"""

import csv
import pickle
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score


ML_DATA_DIR = Path("data/regulation_ml")
MODEL_PATH = ML_DATA_DIR / "regulation_classifier.pkl"


DEPT_KEYWORDS = {
    "품질보증팀": ["품질", "검사", "PPAP", "Cpk", "IATF", "불량", "시정", "8D", "MSA", "SPC"],
    "안전보건팀": ["안전", "소음", "유해", "OSHA", "산안법", "분진", "화재", "보호구", "위험성"],
    "ESG경영팀": ["탄소", "ESG", "CBAM", "환경", "지속가능", "배출", "재활용", "순환"],
    "해외지원팀": ["관세", "IRA", "USMCA", "수출", "통관", "무역", "미국", "EU", "중국"],
    "구매팀": ["REACH", "RoHS", "공급망", "실사", "소재", "화학물질", "협력사", "원자재"],
    "개발본부": ["설계", "인증", "시험", "규격", "기준", "EV", "전기차", "배터리", "안전기준"],
    "생산본부": ["공정", "설비", "작업장", "조업", "생산", "프레스", "용접", "사출"],
}

PLANT_KEYWORDS = {
    "경산본사": ["국내", "경산", "본사", "한국"],
    "경주공장": ["경주", "국내"],
    "JOON INC": ["미국", "조지아", "HMGMA", "IRA", "EWP", "CCH", "관세"],
    "AJIN USA": ["미국", "앨라배마", "관세", "USMCA"],
    "중국법인": ["중국", "상해", "염성", "산동"],
    "베트남법인": ["베트남"],
}


@dataclass
class RegulationRisk:
    """규제 리스크 분류 결과"""
    severity: str                   # HIGH / MEDIUM / LOW
    confidence: float               # 분류 신뢰도 (%)
    all_scores: Dict[str, float]    # 심각도별 확률
    related_departments: List[str]  # 관련 부서
    affected_plants: List[str]      # 영향 시설
    risk_score: int                 # 0~100 리스크 점수
    recommended_actions: List[str]  # 권장 조치
    response_deadline: str = ""     # 권장 대응 기한

    @property
    def affected_facilities(self) -> List[str]:
        """UI 호환 alias (page_compliance.py에서 affected_facilities로 접근)"""
        return self.affected_plants


class RegulationRiskClassifier:
    """TF-IDF + RandomForest 규제 리스크 분류기"""

    def __init__(self):
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.model: Optional[RandomForestClassifier] = None
        self._is_trained = False
        self.accuracy = 0.0

    def train(self, force: bool = False) -> Dict:
        """모델 학습"""
        if not force and MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    cached = pickle.load(f)
                self.vectorizer = cached["vectorizer"]
                self.model = cached["model"]
                self.accuracy = cached["accuracy"]
                self._is_trained = True
                return {"accuracy": self.accuracy, "trained": True}
            except Exception:
                pass

        data_path = ML_DATA_DIR / "regulation_training_data.csv"
        if not data_path.exists():
            raise FileNotFoundError(
                "python -m scripts.generate_regulation_data 를 먼저 실행하세요."
            )

        texts, labels = [], []
        with open(data_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                texts.append(row["text"])
                labels.append(row["severity"])

        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 4),
            max_features=5000, sublinear_tf=True,
        )
        X = self.vectorizer.fit_transform(texts)
        y = np.array(labels)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y,
        )

        self.model = RandomForestClassifier(
            n_estimators=150, max_depth=10,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        self.accuracy = round(accuracy_score(y_test, y_pred), 4)
        self._is_trained = True

        ML_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "model": self.model,
                "accuracy": self.accuracy,
            }, f)

        return {"accuracy": self.accuracy, "trained": True}

    def classify(self, text: str) -> RegulationRisk:
        """규제 텍스트 리스크 분류"""
        if not self._is_trained:
            self.train()

        X = self.vectorizer.transform([text])
        proba = self.model.predict_proba(X)[0]
        classes = self.model.classes_

        all_scores = {cls: round(float(p) * 100, 1) for cls, p in zip(classes, proba)}
        best_idx = np.argmax(proba)
        severity = classes[best_idx]
        confidence = float(proba[best_idx]) * 100

        # 관련 부서 추출
        related_depts = self._extract_departments(text)

        # 영향 시설 추출
        affected = self._extract_plants(text)

        # 리스크 점수
        severity_base = {"HIGH": 80, "MEDIUM": 50, "LOW": 20}
        risk_score = min(100, int(severity_base.get(severity, 50) * (confidence / 100)))

        # 권장 조치
        actions = self._generate_actions(severity, related_depts)

        # 대응 기한 (심각도별)
        deadline_map = {"HIGH": "2주 이내", "MEDIUM": "1개월 이내", "LOW": "분기 �� 검토"}
        deadline = deadline_map.get(severity, "확인 필요")

        return RegulationRisk(
            severity=severity,
            confidence=round(confidence, 1),
            all_scores=all_scores,
            related_departments=related_depts,
            affected_plants=affected,
            risk_score=risk_score,
            recommended_actions=actions,
            response_deadline=deadline,
        )

    def _extract_departments(self, text: str) -> List[str]:
        """텍스트에서 관련 부서 추출"""
        text_lower = text.lower()
        dept_scores = {}
        for dept, keywords in DEPT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                dept_scores[dept] = score
        return sorted(dept_scores, key=dept_scores.get, reverse=True)[:3]

    def _extract_plants(self, text: str) -> List[str]:
        """텍스트에서 영향 시설 추출"""
        text_lower = text.lower()
        plants = []
        for plant, keywords in PLANT_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                plants.append(plant)
        return plants if plants else ["전체 사업장"]

    def _generate_actions(self, severity: str, depts: List[str]) -> List[str]:
        """심각도별 권장 조치 생성"""
        actions = []
        if severity == "HIGH":
            actions.append("즉시 TF(Task Force) 구성 및 긴급 대응 회의 소집")
            actions.append("경영진 보고 및 OEM 통보 검토")
            if depts:
                actions.append(f"주관 부서: {depts[0]} — 대응 계획서 3일 내 수립")
        elif severity == "MEDIUM":
            actions.append("관련 부서 협의체 구성 및 영향도 분석 실시")
            actions.append("대응 일정 수립 (데드라인 역산)")
        else:
            actions.append("동향 모니터링 유지 및 정기 보고에 반영")
            actions.append("관련 교육/세미나 참석 검토")
        return actions


# 싱글턴
_classifier: Optional[RegulationRiskClassifier] = None

def get_regulation_classifier() -> RegulationRiskClassifier:
    global _classifier
    if _classifier is None:
        _classifier = RegulationRiskClassifier()
        _classifier.train()
    return _classifier
