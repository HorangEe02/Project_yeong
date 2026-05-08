"""
ML 기반 에러코드 유사도 검색 엔진
- TF-IDF + 코사인 유사도로 자연어 증상 → 에러코드 매칭
- 한글 동의어/현장 용어 자동 확장
- 장비유형 가중치 필터
- LLM 불필요, 오프라인 동작, 응답 10ms 이내
"""

import sqlite3
import pickle
import os
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

# scikit-learn (pip install scikit-learn)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


ERROR_CODES_DB = "data/equipment/error_codes.db"
MODEL_CACHE_DIR = "data/equipment/ml_cache"


# ──────────────────────────────────────────────
# 1. 현장 동의어 사전 (한글 구어체 → 기술 용어)
# ──────────────────────────────────────────────

SYNONYM_MAP = {
    # 유압 관련
    "기름": "유압 오일",
    "기름이 새": "유압 누유 리크",
    "기름 부족": "유압 오일 부족 레벨",
    "유압 떨어": "유압 압력 저하 드롭",
    "유압 안 올라": "유압 압력 부족 펌프",
    # 전기 관련
    "불 안 들어와": "전원 차단 전기 공급 이상",
    "전기 나가": "전원 차단 정전 브레이커 트립",
    "합선": "단락 쇼트 전기 합선",
    "누전": "누전 접지 이상 절연 저하",
    # 기계 관련
    "소리 나": "소음 이음 진동 이상음",
    "이상한 소리": "이음 진동 소음 비정상",
    "떨림": "진동 이상 밸런스 불량",
    "멈춤": "정지 비상정지 에러 정지",
    "안 움직여": "동작 불가 정지 모터 서보",
    "느려": "속도 저하 응답 지연",
    "뻑뻑": "마찰 윤활 부족 그리스",
    # 온도 관련
    "뜨거워": "과열 온도 상승 오버히트",
    "차가워": "온도 저하 냉각 과다 히터 불량",
    "냉각수": "냉각수 쿨런트 온도",
    "냉갹수": "냉각수 쿨런트",  # 오타 대응
    # 용접 관련
    "용접 안 돼": "용접 불량 미용접 아크 이상",
    "스파크 튀어": "스패터 비산 용접 스파크",
    "너겟 작아": "너겟 부족 직경 미달 가압력",
    "팁 닳았": "전극 마모 팁 교체 드레싱",
    # 로봇 관련
    "로봇 멈춤": "서보 에러 로봇 정지 SRVO",
    "충돌": "충돌 감지 과부하 오버로드",
    "원점 안 잡혀": "원점 복귀 실패 홈 리턴 엔코더",
    "경로 이탈": "경로 편차 프로그램 이상 TCP",
    # 사출 관련
    "제품 안 나와": "사출 미충전 쇼트샷 압력 부족",
    "제품 붙어": "이형 불량 취출 고착",
    "플래시": "플래시 버 형체력 부족",
    "싱크": "싱크마크 수축 보압 부족",
    # CNC 관련
    "치수 안 맞아": "치수 불량 공차 이탈 오프셋",
    "표면 거칠어": "표면 조도 불량 Ra 이상 공구 마모",
    "공구 부러져": "공구 파손 브레이크 절삭조건",
    # 공통
    "과부하": "과부하 오버로드 과전류",
    "에러": "에러 알람 이상 경고",
    "경고": "경고 워닝 주의 알람",
    "비상정지": "비상정지 이머전시 E-STOP",
}

# v3.4: 설비 유형별 전문 증상 동의어 사전 (40개 카테고리, 각 4~5개 동의어)
EQUIPMENT_SYMPTOM_SYNONYMS = {
    # ─── 프레스 (press) ───
    "슬라이드 편차": "슬라이드 위치 이상 하사점 편차 BDC 편차 스트로크 이상 슬라이드 틀어짐",
    "유압 압력 저하": "유압 낮음 유압 부족 오일 압력 저하 유압계 이상 펌프 압력 부족",
    "클러치 슬립": "클러치 미끄러짐 클러치 공회전 클러치 마모 브레이크 슬립",
    "쿠션 이상": "다이쿠션 이상 쿠션압 부족 쿠션 불균일 에어쿠션 이상",
    "소음 진동": "프레스 소음 이상 소리 진동 심함 떨림 발생 타격음 이상",
    "소재 이송 불량": "피더 이상 코일 이송 불량 레벨러 이상 언코일러 걸림 소재 걸림",
    "금형 파손": "다이 깨짐 펀치 파손 금형 크랙 다이 마모",
    "제품 성형 불량": "성형 불량 크랙 발생 주름 발생 스프링백 과다 드로잉 불량",
    # ─── 용접기 (welder) ───
    "아크 불안정": "아크 끊김 아크 튐 용접 불꽃 튐 아크 불량",
    "스패터 과다": "스패터 많이 나옴 튀김 심함 비산물 과다 용접 튀김",
    "너겟 불량": "너겟 미형성 용접 강도 부족 너겟 크기 미달 너겟 편심",
    "전극 마모": "전극 닳음 전극 변형 팁 마모 전극 드레싱 필요",
    "냉각수 순환 이상": "냉각수 부족 냉각수 온도 높음 워터 플로우 이상 냉각 라인 막힘",
    "용접 전류 이상": "전류 불안정 전류 낮음 전류 과대 용접기 출력 이상",
    "용접 위치 틀어짐": "용접 포인트 이탈 타점 위치 이상 건 위치 오프셋",
    # ─── 로봇 (robot) ───
    "서보 이상": "서보 모터 이상 서보 에러 서보 과부하 모터 과열",
    "축 편차": "축 위치 이상 엔코더 이상 위치 정밀도 저하 반복 정밀도 불량",
    "그리퍼 불량": "집게 이상 클램프 불량 그리퍼 미동작 소재 탈락",
    "충돌 감지": "로봇 충돌 간섭 발생 비상 정지 충격 감지",
    "통신 에러": "이더넷 끊김 필드버스 에러 PLC 통신 이상 네트워크 단절",
    "티칭 오류": "프로그램 오류 경로 이상 티칭 재작업 필요 궤적 에러",
    # ─── 사출기 (injection) ───
    "사출 압력 이상": "사출 압력 부족 보압 이상 사출 속도 불안정",
    "형체력 부족": "형체 압력 저하 금형 벌어짐 플래시 발생",
    "냉각 불균일": "냉각 편차 제품 변형 싱크마크 웰드라인",
    "호퍼 막힘": "원료 공급 불량 호퍼 브릿지 피더 막힘",
    "노즐 막힘": "노즐 클로깅 게이트 막힘 콜드 슬러그",
    # ─── CNC ───
    "절삭 진동": "채터링 가공면 울림 떨림 가공 채터 마크",
    "공구 마모": "인서트 마모 드릴 마모 엔드밀 마모 공구 파손",
    "치수 편차": "가공 치수 불량 공차 이탈 정밀도 저하 영점 틀어짐",
    "칩 배출 불량": "칩 감김 칩 막힘 칩 배출 이상 칩 브레이커 불량",
    "주축 이상": "스핀들 이상 주축 진동 스핀들 과열 베어링 소음",
    # ─── 레이저 ───
    "레이저 출력 저하": "광량 부족 레이저 파워 감소 빔 약해짐",
    "초점 이상": "포커스 이상 초점 거리 틀어짐 빔 퍼짐",
    "가스 압력 이상": "어시스트 가스 부족 질소 압력 저하 가스 누출",
    "절단면 품질 불량": "버 발생 드로스 발생 절단면 거침 열 영향부 과대",
    # ─── 공통 (common) ───
    "센서 이상": "근접 센서 불량 리밋 스위치 이상 포토센서 오감지 센서 미감지",
    "PLC 에러": "래더 오류 프로그램 에러 출력 미동작 입력 미감지",
    "전원 이상": "전압 불안정 전원 차단 UPS 이상 순간 정전",
    "에어 압력 이상": "공압 부족 에어 누출 컴프레서 이상 에어 드라이어 불량",
    "온도 이상": "과열 온도 높음 온도 낮음 히터 불량 냉각 불량",
}

# v3.4: 장비 유형별 증상 카테고리 맵 (UI 드롭박스용)
EQUIPMENT_SYMPTOM_CATEGORIES = {
    "프레스": ["슬라이드 편차", "유압 압력 저하", "클러치 슬립", "쿠션 이상",
               "소음 진동", "소재 이송 불량", "금형 파손", "제품 성형 불량"],
    "용접기": ["아크 불안정", "스패터 과다", "너겟 불량", "전극 마모",
               "냉각수 순환 이상", "용접 전류 이상", "용접 위치 틀어짐"],
    "로봇": ["서보 이상", "축 편차", "그리퍼 불량", "충돌 감지", "통신 에러", "티칭 오류"],
    "사출기": ["사출 압력 이상", "형체력 부족", "냉각 불균일", "호퍼 막힘", "노즐 막힘"],
    "CNC": ["절삭 진동", "공구 마모", "치수 편차", "칩 배출 불량", "주축 이상"],
    "레이저": ["레이저 출력 저하", "초점 이상", "가스 압력 이상", "절단면 품질 불량"],
    "공통": ["센서 이상", "PLC 에러", "전원 이상", "에어 압력 이상", "온도 이상"],
}


# ──────────────────────────────────────────────
# 2. 에러코드 데이터 로더
# ──────────────────────────────────────────────

@dataclass
class ErrorCodeEntry:
    """에러코드 항목"""
    code: str
    equipment_type: str
    category: str
    description: str
    cause: str
    action: str
    severity: str
    # ML 검색용 결합 텍스트
    search_text: str = ""


def load_error_codes(db_path: str = ERROR_CODES_DB) -> List[ErrorCodeEntry]:
    """error_codes.db에서 전체 에러코드 로드"""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute("SELECT * FROM error_codes").fetchall()
    except Exception:
        conn.close()
        return []

    entries = []
    for row in rows:
        r = dict(row)
        code = r.get("code", r.get("error_code", ""))
        eq_type = r.get("equipment_type", "")
        category = r.get("category", "")
        desc = r.get("description", "")
        cause = r.get("cause", r.get("possible_cause", ""))
        action = r.get("action", r.get("recommended_action", ""))
        severity = r.get("severity", "")

        # 검색용 텍스트: 모든 필드를 결합 (가중치 반영을 위해 중요 필드 반복)
        search_text = " ".join([
            desc, desc,          # description 2x 가중
            cause, cause,        # cause 2x 가중
            action,              # action 1x
            eq_type,             # 장비유형
            category,            # 카테고리
            code,                # 코드 자체
        ])

        entries.append(ErrorCodeEntry(
            code=code,
            equipment_type=eq_type,
            category=category,
            description=desc,
            cause=cause,
            action=action,
            severity=severity,
            search_text=search_text,
        ))

    conn.close()
    return entries


# ──────────────────────────────────────────────
# 3. TF-IDF 모델 빌드 + 캐시
# ──────────────────────────────────────────────

class ErrorCodeMLSearchEngine:
    """
    ML 기반 에러코드 검색 엔진

    사용법:
        engine = ErrorCodeMLSearchEngine()
        engine.build_index()  # 최초 1회 또는 데이터 변경 시
        results = engine.search("프레스가 멈추고 유압 경고등이 켜짐", top_k=5)
    """

    def __init__(self, db_path: str = ERROR_CODES_DB):
        self.db_path = db_path
        self.entries: List[ErrorCodeEntry] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self._cache_path = Path(MODEL_CACHE_DIR)
        self._cache_path.mkdir(parents=True, exist_ok=True)

    def build_index(self, force: bool = False) -> int:
        """
        TF-IDF 인덱스 빌드 (캐시 있으면 로드)

        Returns:
            인덱싱된 에러코드 수
        """
        cache_file = self._cache_path / "tfidf_model.pkl"

        # 캐시 로드 시도
        if not force and cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    cached = pickle.load(f)
                self.entries = cached["entries"]
                self.vectorizer = cached["vectorizer"]
                self.tfidf_matrix = cached["tfidf_matrix"]
                return len(self.entries)
            except Exception:
                pass  # 캐시 손상 → 재빌드

        # 데이터 로드
        self.entries = load_error_codes(self.db_path)
        if not self.entries:
            return 0

        # TF-IDF 벡터화
        corpus = [e.search_text for e in self.entries]

        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",  # 한글 형태소 분석기 없이도 동작하는 문자 n-gram
            ngram_range=(2, 4),  # 2~4글자 단위 (한글 2음절~4음절)
            max_features=5000,
            sublinear_tf=True,   # TF에 로그 스케일 적용
            min_df=1,            # 최소 문서 빈도 (201건이므로 낮게)
            max_df=0.95,         # 95% 이상 문서에 등장하는 토큰 제외
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

        # 캐시 저장
        try:
            with open(cache_file, "wb") as f:
                pickle.dump({
                    "entries": self.entries,
                    "vectorizer": self.vectorizer,
                    "tfidf_matrix": self.tfidf_matrix,
                }, f)
        except Exception:
            pass

        return len(self.entries)

    def search(
        self,
        query: str,
        top_k: int = 5,
        equipment_filter: str = None,
        min_score: float = 0.05,
    ) -> List[Dict]:
        """
        자연어 증상으로 에러코드 검색

        Args:
            query: 자연어 증상 설명 (예: "프레스가 멈추고 유압 경고등이 켜짐")
            top_k: 반환할 최대 결과 수
            equipment_filter: 장비유형 필터 (예: "프레스", None이면 전체)
            min_score: 최소 유사도 점수 (이하 결과 제외)

        Returns:
            [{code, equipment_type, description, cause, action, severity, score, rank}, ...]
        """
        if self.vectorizer is None or self.tfidf_matrix is None:
            self.build_index()

        if not self.entries:
            return []

        # 쿼리 전처리: 동의어 확장
        expanded_query = self._expand_synonyms(query)

        # 쿼리 벡터화
        query_vec = self.vectorizer.transform([expanded_query])

        # 코사인 유사도 계산
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # 장비유형 필터 가중치
        if equipment_filter:
            filter_lower = equipment_filter.lower()
            for i, entry in enumerate(self.entries):
                if filter_lower in entry.equipment_type.lower():
                    similarities[i] *= 1.3  # 매칭 장비유형 30% 부스트
                else:
                    similarities[i] *= 0.7  # 비매칭 30% 감소

        # 정렬 (내림차순)
        ranked_indices = similarities.argsort()[::-1]

        results = []
        for rank, idx in enumerate(ranked_indices[:top_k * 2]):  # 필터 후 줄어들 수 있으므로 넉넉히
            score = float(similarities[idx])
            if score < min_score:
                break

            entry = self.entries[idx]

            # 장비유형 필터 (엄격 모드)
            if equipment_filter and equipment_filter.lower() not in entry.equipment_type.lower():
                if score < min_score * 2:  # 점수가 낮으면서 필터 불일치 → 제외
                    continue

            results.append({
                "code": entry.code,
                "equipment_type": entry.equipment_type,
                "category": entry.category,
                "description": entry.description,
                "cause": entry.cause,
                "action": entry.action,
                "severity": entry.severity,
                "score": round(score, 4),
                "rank": len(results) + 1,
                "match_type": "ml_similarity",
            })

            if len(results) >= top_k:
                break

        return results

    def _expand_synonyms(self, query: str) -> str:
        """동의어 사전으로 쿼리 확장 (v3.4: EQUIPMENT_SYMPTOM_SYNONYMS 추가)"""
        expanded = query
        q_lower = query.lower()

        # 기존 범용 동의어
        for colloquial, technical in SYNONYM_MAP.items():
            if colloquial in q_lower:
                expanded += " " + technical

        # v3.4: 설비별 전문 동의어
        for symptom_key, synonyms_text in EQUIPMENT_SYMPTOM_SYNONYMS.items():
            if symptom_key in q_lower:
                expanded += " " + synonyms_text

        return expanded

    def get_similar_codes(self, error_code: str, top_k: int = 5) -> List[Dict]:
        """
        특정 에러코드와 유사한 다른 에러코드 검색

        Args:
            error_code: 기준 에러코드 (예: "HYD-001")
            top_k: 반환할 유사 코드 수

        Returns:
            유사 에러코드 리스트 (자기 자신 제외)
        """
        if self.tfidf_matrix is None:
            self.build_index()

        # 기준 에러코드 인덱스 찾기
        target_idx = None
        for i, entry in enumerate(self.entries):
            if entry.code == error_code:
                target_idx = i
                break

        if target_idx is None:
            return []

        # 해당 코드의 벡터와 전체 비교
        target_vec = self.tfidf_matrix[target_idx]
        similarities = cosine_similarity(target_vec, self.tfidf_matrix)[0]

        # 자기 자신 제외하고 정렬
        ranked = sorted(
            [(i, similarities[i]) for i in range(len(self.entries)) if i != target_idx],
            key=lambda x: x[1],
            reverse=True,
        )

        results = []
        for idx, score in ranked[:top_k]:
            entry = self.entries[idx]
            results.append({
                "code": entry.code,
                "equipment_type": entry.equipment_type,
                "description": entry.description,
                "similarity": round(float(score), 4),
            })

        return results

    def get_stats(self) -> Dict:
        """엔진 통계 정보"""
        if not self.entries:
            return {"total_codes": 0, "vocab_size": 0, "index_built": False}

        return {
            "total_codes": len(self.entries),
            "vocab_size": len(self.vectorizer.vocabulary_) if self.vectorizer else 0,
            "equipment_types": list(set(e.equipment_type for e in self.entries)),
            "categories": list(set(e.category for e in self.entries)),
            "index_built": self.tfidf_matrix is not None,
            "synonym_count": len(SYNONYM_MAP) + len(EQUIPMENT_SYMPTOM_SYNONYMS),
        }


# ──────────────────────────────────────────────
# 4. 모듈 레벨 싱글턴 (앱 전역에서 재사용)
# ──────────────────────────────────────────────

_engine_instance: Optional[ErrorCodeMLSearchEngine] = None

def get_ml_search_engine() -> ErrorCodeMLSearchEngine:
    """싱글턴 ML 검색 엔진 인스턴스"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ErrorCodeMLSearchEngine()
        _engine_instance.build_index()
    return _engine_instance


def ml_search_error_codes(
    query: str,
    top_k: int = 5,
    equipment_filter: str = None,
) -> List[Dict]:
    """간편 검색 함수 (UI에서 직접 호출)"""
    engine = get_ml_search_engine()
    return engine.search(query, top_k=top_k, equipment_filter=equipment_filter)


def ml_find_similar_codes(error_code: str, top_k: int = 5) -> List[Dict]:
    """간편 유사 코드 검색"""
    engine = get_ml_search_engine()
    return engine.get_similar_codes(error_code, top_k=top_k)


# ──────────────────────────────────────────────
# v3.4: 통합 컨텍스트 검색 (이력 + Markov 연쇄)
# ──────────────────────────────────────────────

def ml_search_with_context(
    query: str,
    top_k: int = 5,
    equipment_filter: str = None,
) -> List[Dict]:
    """검색 결과 + 이력 요약 + 연쇄 고장 경고 통합 (v3.4)

    각 결과에 'history_summary' 키가 추가되며,
    TOP-1 결과에만 'cascade_warning' 키가 추가된다.
    """
    results = ml_search_error_codes(query, top_k=top_k, equipment_filter=equipment_filter)
    if not results:
        return results

    # 이력 DB 연동
    try:
        from features.equipment.error_history_db import get_error_history_db
        history_db = get_error_history_db()
    except Exception:
        history_db = None

    # Markov 연쇄 예측 (TOP-1만)
    cascade_warning = None
    try:
        from features.equipment.markov_predictor import get_markov_predictor
        predictor = get_markov_predictor()
        if hasattr(predictor, "_is_trained") and predictor._is_trained:
            top_code = results[0]["code"]
            analysis = predictor.predict_next(top_code)
            if analysis and analysis.next_predictions:
                cascade_warning = {
                    "current_code": top_code,
                    "predictions": [
                        {
                            "code": p.code,
                            "probability": p.probability,
                            "description": p.description,
                            "expected_delay_hours": p.expected_delay_hours,
                        }
                        for p in analysis.next_predictions[:3]
                    ],
                    "risk_level": analysis.risk_level,
                    "prevention_message": analysis.prevention_message,
                }
    except Exception:
        pass

    # 결과에 컨텍스트 첨부
    for i, r in enumerate(results):
        # 이력 요약
        if history_db:
            try:
                r["history_summary"] = history_db.get_summary(r["code"], months=3)
            except Exception:
                r["history_summary"] = None
        else:
            r["history_summary"] = None

        # 연쇄 경고 (TOP-1만)
        r["cascade_warning"] = cascade_warning if i == 0 else None

    return results


# ──────────────────────────────────────────────
# v3.4: 검색 피드백 수집
# ──────────────────────────────────────────────

_FEEDBACK_DB_PATH = Path("data/equipment/search_feedback.db")


def save_feedback(query: str, error_code: str, helpful: bool) -> None:
    """검색 결과에 대한 사용자 피드백 저장 (v3.4)"""
    import sqlite3

    _FEEDBACK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(_FEEDBACK_DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                error_code TEXT NOT NULL,
                helpful INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "INSERT INTO search_feedback (query, error_code, helpful) VALUES (?, ?, ?)",
            (query, error_code, 1 if helpful else 0),
        )
