"""
에러코드 인과관계 정의 + 합성 이벤트 시퀀스 생성기
- 7장비유형 × 카테고리 기반 인과관계 규칙 ~70건 정의
- 마르코프 학습용 합성 이벤트 시퀀스 생성
"""

import numpy as np
import sqlite3
import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta


ERROR_CODES_DB = "data/equipment/error_codes.db"
OUTPUT_DIR = Path("data/markov_ml")


# ──────────────────────────────────────────────
# 1. 에러코드 인과관계 규칙 (도메인 지식)
# ──────────────────────────────────────────────
# 형식: "원인 카테고리" → [("결과 카테고리", 전이 확률, 지연 시간 범위(시간))]
# 카테고리 수준으로 정의 → 개별 에러코드로 전개

CAUSALITY_RULES = {
    # ── 프레스 연쇄 ──
    "HYD": [
        ("MEC", 0.35, (1, 12)),     # 유압 이상 → 기계적 문제 (35%, 1~12시간 후)
        ("SAF", 0.25, (0, 4)),      # 유압 이상 → 안전 정지 (25%, 즉시~4시간)
        ("QUA", 0.20, (2, 24)),     # 유압 이상 → 품질 불량 (20%, 2~24시간)
        ("ELC", 0.10, (4, 24)),     # 유압 이상 → 전기 문제 (10%, 연쇄 열화)
    ],
    "ELC": [
        ("SAF", 0.30, (0, 2)),      # 전기 이상 → 안전 정지
        ("AUT", 0.25, (0, 4)),      # 전기 이상 → 자동화 이상
        ("HYD", 0.15, (2, 12)),     # 전기 이상 → 유압 펌프 영향
    ],
    "MEC": [
        ("QUA", 0.40, (0, 8)),      # 기계 이상 → 품질 불량
        ("SAF", 0.20, (0, 2)),      # 기계 이상 → 안전 정지
        ("LUB", 0.15, (4, 24)),     # 기계 이상 → 윤활 부족 감지
    ],
    "LUB": [
        ("MEC", 0.45, (4, 48)),     # 윤활 부족 → 기계 마모 가속
        ("HYD", 0.20, (2, 24)),     # 윤활 → 유압 영향
    ],
    "SAF": [
        ("AUT", 0.15, (0, 1)),      # 안전 정지 후 → 자동화 리셋 실패
    ],

    # ── 용접기 연쇄 ──
    "CLG": [
        ("WLD", 0.40, (1, 8)),      # 냉각 이상 → 용접 품질 저하
        ("TIP", 0.30, (2, 12)),     # 냉각 이상 → 전극 과열 마모
        ("MON", 0.15, (0, 4)),      # 냉각 이상 → 모니터링 경고
    ],
    "WLD": [
        ("QUA", 0.45, (0, 4)),      # 용접 이상 → 품질 불량 (너겟 부족 등)
        ("PRS", 0.20, (2, 12)),     # 용접 이상 → 가압 점검
        ("TIP", 0.15, (4, 24)),     # 용접 이상 → 전극 점검
    ],
    "TIP": [
        ("WLD", 0.50, (0, 4)),      # 전극 마모 → 용접 불량
        ("GUN", 0.20, (2, 12)),     # 전극 마모 → 건 정비
    ],
    "PRS": [
        ("WLD", 0.35, (0, 4)),      # 가압력 이상 → 용접 불량
        ("CLG", 0.15, (2, 12)),     # 가압 이상 → 냉각 부하 증가
    ],

    # ── 로봇 연쇄 ──
    "SRVO": [
        ("MOTN", 0.40, (0, 2)),     # 서보 에러 → 동작 이상
        ("SYST", 0.25, (0, 4)),     # 서보 에러 → 시스템 에러
        ("WAPP", 0.15, (1, 8)),     # 서보 에러 → 용접 적용 이상
    ],
    "MOTN": [
        ("SRVO", 0.30, (0, 4)),     # 동작 이상 → 서보 과부하
        ("APSH", 0.20, (0, 4)),     # 동작 이상 → 응용 에러
        ("EXT", 0.15, (2, 12)),     # 동작 이상 → 외부축 영향
    ],
    "SYST": [
        ("SRVO", 0.35, (0, 2)),     # 시스템 에러 → 서보 리셋
        ("APSH", 0.20, (0, 4)),     # 시스템 에러 → 응용 프로그램
    ],

    # ── 사출기 연쇄 ──
    "TEMP": [
        ("INJ", 0.35, (1, 8)),      # 온도 이상 → 사출 불량
        ("PRD", 0.30, (2, 12)),     # 온도 이상 → 제품 불량
        ("MLD", 0.20, (4, 24)),     # 온도 이상 → 금형 변형
    ],
    "INJ": [
        ("PRD", 0.45, (0, 4)),      # 사출 이상 → 제품 불량
        ("CLP", 0.15, (2, 12)),     # 사출 이상 → 형체 문제
    ],
    "CLP": [
        ("PRD", 0.30, (0, 8)),      # 형체 이상 → 제품 불량 (플래시)
        ("MLD", 0.25, (4, 24)),     # 형체 이상 → 금형 손상
    ],
    "MAT": [
        ("INJ", 0.40, (0, 4)),      # 소재 이상 → 사출 불량
        ("TEMP", 0.20, (1, 8)),     # 소재 이상 → 온도 이상
    ],

    # ── 공통설비 연쇄 ──
    "COM-E": [
        ("COM-U", 0.25, (0, 4)),    # 전기 → 유틸리티
        ("COM-S", 0.30, (0, 2)),    # 전기 → 안전
    ],
    "COM-U": [
        ("COM-E", 0.20, (2, 12)),   # 유틸 → 전기 영향
        ("COM-S", 0.15, (0, 4)),    # 유틸 → 안전
    ],

    # ── 크로스 장비 연쇄 (간접) ──
    "QUA": [
        ("COM-M", 0.25, (0, 8)),    # 품질 불량 → 검사 장비 확인
    ],
}


def load_error_code_map(db_path: str = ERROR_CODES_DB) -> Dict[str, List[str]]:
    """카테고리 → 에러코드 리스트 매핑 로드"""
    if not Path(db_path).exists():
        return {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    category_map = {}
    try:
        for row in conn.execute("SELECT code, category FROM error_codes"):
            r = dict(row)
            cat = r.get("category", "")
            code = r.get("code", "")
            if cat not in category_map:
                category_map[cat] = []
            category_map[cat].append(code)
    except Exception:
        pass

    conn.close()
    return category_map


def generate_event_sequences(
    n_sequences: int = 5000,
    min_length: int = 3,
    max_length: int = 8,
    seed: int = 42,
) -> List[List[Dict]]:
    """
    마르코프 학습용 합성 이벤트 시퀀스 생성

    각 시퀀스: 초기 에러코드 → 인과관계에 따른 연쇄 이벤트 리스트

    Returns:
        [[{"code": "HYD-001", "category": "HYD", "time": "2026-01-01 08:00"}, ...], ...]
    """
    np.random.seed(seed)
    category_map = load_error_code_map()

    if not category_map:
        # DB 없으면 더미 카테고리 맵 사용
        category_map = _generate_dummy_category_map()

    all_categories = list(CAUSALITY_RULES.keys())
    sequences = []

    for _ in range(n_sequences):
        # 초기 에러코드: 랜덤 카테고리에서 시작
        start_cat = np.random.choice(all_categories)
        codes_in_cat = category_map.get(start_cat, [f"{start_cat}-001"])
        start_code = np.random.choice(codes_in_cat)

        base_time = datetime(2026, 1, 1, 8, 0, 0) + timedelta(
            days=np.random.randint(0, 180),
            hours=np.random.randint(0, 16),
        )

        sequence = [{
            "code": start_code,
            "category": start_cat,
            "equipment_type": _infer_equipment_type(start_cat),
            "timestamp": base_time.isoformat(),
        }]

        current_cat = start_cat
        current_time = base_time
        seq_length = np.random.randint(min_length, max_length + 1)

        for step in range(seq_length - 1):
            rules = CAUSALITY_RULES.get(current_cat, [])
            if not rules:
                break

            # 전이 확률에 따라 다음 카테고리 선택
            next_cats = [r[0] for r in rules]
            probs = np.array([r[1] for r in rules])

            # 전이 없을 확률 (잔여)
            no_transition_prob = max(0, 1.0 - probs.sum())
            all_options = next_cats + ["_END"]
            all_probs = np.append(probs, no_transition_prob)
            all_probs = all_probs / all_probs.sum()  # 정규화

            chosen = np.random.choice(all_options, p=all_probs)
            if chosen == "_END":
                break

            # 지연 시간
            rule = next((r for r in rules if r[0] == chosen), None)
            if rule:
                delay_hours = np.random.uniform(rule[2][0], rule[2][1])
            else:
                delay_hours = np.random.uniform(1, 12)

            current_time += timedelta(hours=delay_hours)
            current_cat = chosen

            codes_in_cat = category_map.get(current_cat, [f"{current_cat}-001"])
            next_code = np.random.choice(codes_in_cat)

            sequence.append({
                "code": next_code,
                "category": current_cat,
                "equipment_type": _infer_equipment_type(current_cat),
                "timestamp": current_time.isoformat(),
            })

        if len(sequence) >= 2:
            sequences.append(sequence)

    return sequences


def save_sequences(sequences: List, output_path: str = None):
    """시퀀스를 JSON으로 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = str(OUTPUT_DIR / "event_sequences.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sequences, f, ensure_ascii=False, indent=2)

    total_events = sum(len(s) for s in sequences)
    print(f"이벤트 시퀀스 저장: {len(sequences)}건, 총 {total_events}이벤트 → {output_path}")


def _infer_equipment_type(category: str) -> str:
    """카테고리에서 장비유형 추론"""
    mapping = {
        "HYD": "프레스", "ELC": "프레스", "MEC": "프레스", "SAF": "프레스",
        "QUA": "프레스", "AUT": "프레스", "LUB": "프레스",
        "WLD": "용접기", "PRS": "용접기", "CLG": "용접기", "TIP": "용접기",
        "GUN": "용접기", "MON": "용접기",
        "SRVO": "로봇", "SYST": "로봇", "APSH": "로봇", "MOTN": "로봇",
        "WAPP": "로봇", "EXT": "로봇",
        "TEMP": "사출기", "INJ": "사출기", "CLP": "사출기", "PRD": "사출기",
        "AUX": "사출기", "MAT": "사출기", "MLD": "사출기",
        "COM-E": "공통설비", "COM-U": "공통설비", "COM-S": "공통설비",
        "COM-M": "공통설비", "COM-L": "공통설비", "COM-I": "공통설비",
    }
    return mapping.get(category, "공통설비")


def _generate_dummy_category_map() -> Dict[str, List[str]]:
    """error_codes.db 없을 때 더미 매핑"""
    dummy = {}
    for cat in CAUSALITY_RULES.keys():
        dummy[cat] = [f"{cat}-{i:03d}" for i in range(1, 6)]
    return dummy


if __name__ == "__main__":
    print("마르코프 학습용 이벤트 시퀀스 생성...")
    seqs = generate_event_sequences(n_sequences=5000)
    save_sequences(seqs)
    print("완료!")
