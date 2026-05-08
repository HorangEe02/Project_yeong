"""
ML 기반 경량 의도 분류기
- TF-IDF + LogisticRegression (scikit-learn)
- 5개 의도 분류 + 신뢰도 점수
- 기존 키워드 분류기와 앙상블 가능
- LLM 불필요, 오프라인 동작, ~5ms/쿼리
"""

import csv
import pickle
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score


logger = logging.getLogger(__name__)

ML_DATA_DIR = Path("data/intent_ml")
MODEL_PATH = ML_DATA_DIR / "intent_classifier.pkl"

INTENT_LABELS = {
    "employee_lookup": "인원 검색",
    "company_info": "회사 정보",
    "document_search": "문서 검색",
    "document_compose": "문서 작성",
    "regulation_query": "규제 조회",
}


@dataclass
class IntentPrediction:
    """의도 분류 결과"""
    intent: str                 # 예측된 의도
    intent_label: str           # 한글 레이블
    confidence: float           # 신뢰도 (0~100%)
    all_scores: Dict[str, float]  # 전 의도별 확률
    method: str                 # "ml" / "keyword" / "llm_fallback"


@dataclass
class ClassifierMetrics:
    """분류기 성능 지표"""
    accuracy: float
    cv_score_mean: float        # 5-fold CV 평균
    cv_score_std: float
    train_size: int
    test_size: int
    per_class_f1: Dict[str, float]


class MLIntentClassifier:
    """TF-IDF + LogisticRegression 의도 분류기"""

    def __init__(self):
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.model: Optional[LogisticRegression] = None
        self.metrics: Optional[ClassifierMetrics] = None
        self._is_trained = False

    def train(self, data_path: str = None, force: bool = False) -> ClassifierMetrics:
        """모델 학습"""

        # 캐시 로드
        if not force and MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    cached = pickle.load(f)
                self.vectorizer = cached["vectorizer"]
                self.model = cached["model"]
                self.metrics = cached["metrics"]
                self._is_trained = True
                logger.info("의도 분류 ML 모델 캐시 로드 완료")
                return self.metrics
            except Exception:
                pass

        # 데이터 로드
        if data_path is None:
            data_path = str(ML_DATA_DIR / "intent_training_data.csv")

        if not Path(data_path).exists():
            raise FileNotFoundError(
                f"학습 데이터 없음: {data_path}\n"
                "python -m scripts.generate_intent_data 를 먼저 실행하세요."
            )

        texts, labels = [], []
        with open(data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                texts.append(row["text"])
                labels.append(row["intent"])

        # TF-IDF 벡터화 (char_wb n-gram — 한글에 효과적)
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            max_features=8000,
            sublinear_tf=True,
            min_df=2,
            max_df=0.95,
        )

        X = self.vectorizer.fit_transform(texts)
        y = np.array(labels)

        # Train/Test 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y,
        )

        # LogisticRegression (다중 클래스)
        self.model = LogisticRegression(
            C=5.0,
            max_iter=1000,
            multi_class="multinomial",
            solver="lbfgs",
            class_weight="balanced",
            random_state=42,
        )
        self.model.fit(X_train, y_train)

        # 평가
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # 5-fold Cross Validation
        cv_scores = cross_val_score(self.model, X, y, cv=5, scoring="accuracy")

        # Per-class F1
        report = classification_report(y_test, y_pred, output_dict=True)
        per_class_f1 = {
            intent: round(report[intent]["f1-score"], 3)
            for intent in INTENT_LABELS.keys()
            if intent in report
        }

        self.metrics = ClassifierMetrics(
            accuracy=round(accuracy, 4),
            cv_score_mean=round(cv_scores.mean(), 4),
            cv_score_std=round(cv_scores.std(), 4),
            train_size=X_train.shape[0],
            test_size=X_test.shape[0],
            per_class_f1=per_class_f1,
        )

        self._is_trained = True

        # 캐시 저장
        ML_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "model": self.model,
                "metrics": self.metrics,
            }, f)

        logger.info(
            f"의도 분류 ML 모델 학습 완료 — "
            f"Accuracy: {accuracy:.1%}, CV: {cv_scores.mean():.1%}"
        )
        return self.metrics

    def predict(self, text: str) -> IntentPrediction:
        """단일 텍스트 의도 분류"""
        if not self._is_trained:
            self.train()

        X = self.vectorizer.transform([text])

        # 확률 분포
        proba = self.model.predict_proba(X)[0]
        classes = self.model.classes_

        all_scores = {
            cls: round(float(prob) * 100, 1)
            for cls, prob in zip(classes, proba)
        }

        # 최고 확률 의도
        best_idx = np.argmax(proba)
        best_intent = classes[best_idx]
        best_confidence = float(proba[best_idx]) * 100

        return IntentPrediction(
            intent=best_intent,
            intent_label=INTENT_LABELS.get(best_intent, best_intent),
            confidence=round(best_confidence, 1),
            all_scores=all_scores,
            method="ml",
        )

    def predict_batch(self, texts: List[str]) -> List[IntentPrediction]:
        """배치 분류"""
        if not self._is_trained:
            self.train()

        X = self.vectorizer.transform(texts)
        probas = self.model.predict_proba(X)
        classes = self.model.classes_

        results = []
        for proba in probas:
            all_scores = {cls: round(float(p) * 100, 1) for cls, p in zip(classes, proba)}
            best_idx = np.argmax(proba)
            results.append(IntentPrediction(
                intent=classes[best_idx],
                intent_label=INTENT_LABELS.get(classes[best_idx], ""),
                confidence=round(float(proba[best_idx]) * 100, 1),
                all_scores=all_scores,
                method="ml",
            ))
        return results

    def get_stats(self) -> Dict:
        """모델 통계"""
        return {
            "is_trained": self._is_trained,
            "vocab_size": len(self.vectorizer.vocabulary_) if self.vectorizer else 0,
            "n_classes": len(self.model.classes_) if self.model else 0,
            "accuracy": self.metrics.accuracy if self.metrics else 0,
            "cv_score": f"{self.metrics.cv_score_mean:.1%} +/- {self.metrics.cv_score_std:.1%}" if self.metrics else "",
        }


# ──────────────────────────────────────────────
# 앙상블: ML + 기존 키워드 결합
# ──────────────────────────────────────────────

def classify_intent_hybrid(
    query: str,
    ml_weight: float = 0.7,
    keyword_weight: float = 0.3,
    ml_confidence_threshold: float = 70.0,
) -> IntentPrediction:
    """
    ML + 키워드 앙상블 의도 분류

    Args:
        query: 사용자 질문
        ml_weight: ML 분류기 가중치 (0~1)
        keyword_weight: 키워드 분류기 가중치 (0~1)
        ml_confidence_threshold: ML 단독 판정 최소 신뢰도 (%)

    Returns:
        IntentPrediction
    """
    classifier = get_ml_classifier()

    # ML 분류
    ml_result = classifier.predict(query)

    # ML 신뢰도가 충분히 높으면 즉시 반환
    if ml_result.confidence >= ml_confidence_threshold:
        return ml_result

    # ML 신뢰도 부족 -> 키워드 점수와 앙상블
    try:
        from features.search.intent_router import _keyword_scoring

        keyword_scores = _keyword_scoring(query)
        sorted_kw = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
        keyword_intent = sorted_kw[0][0] if sorted_kw[0][1] > 0 else None

        if keyword_intent:
            if keyword_intent == ml_result.intent:
                # ML과 키워드 일치 -> 신뢰도 부스트
                ml_result.confidence = min(99.0, ml_result.confidence + 15)
                ml_result.method = "ml+keyword"
                return ml_result
            elif ml_result.confidence >= 50:
                # ML 신뢰도 50% 이상이면 ML 우선
                ml_result.method = "ml"
                return ml_result
            else:
                # ML 신뢰도 낮고 키워드와 불일치 -> 키워드 결과
                return IntentPrediction(
                    intent=keyword_intent,
                    intent_label=INTENT_LABELS.get(keyword_intent, keyword_intent),
                    confidence=55.0,
                    all_scores=ml_result.all_scores,
                    method="keyword",
                )
    except Exception:
        pass

    return ml_result


# ──────────────────────────────────────────────
# 싱글턴
# ──────────────────────────────────────────────

_classifier_instance: Optional[MLIntentClassifier] = None


def get_ml_classifier() -> MLIntentClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = MLIntentClassifier()
        try:
            _classifier_instance.train()
        except FileNotFoundError:
            logger.warning("의도 분류 학습 데이터 없음 — ML 분류기 비활성")
    return _classifier_instance
