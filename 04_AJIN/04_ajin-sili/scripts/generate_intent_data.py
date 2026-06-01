"""
의도 분류 ML 학습용 합성 데이터 생성기
- 5개 의도별 템플릿 기반 합성
- 기존 키워드 패턴을 슬롯 채우기로 확장
- 오타/줄임말/구어체 변형(augmentation) 포함
- 의도당 300건 x 5 = 1,500건 생성
"""

import random
import json
import csv
from pathlib import Path
from typing import List, Dict


OUTPUT_DIR = Path("data/intent_ml")

# ──────────────────────────────────────────────
# 슬롯 채우기용 데이터
# ──────────────────────────────────────────────

PERSON_NAMES = ["김", "이", "박", "최", "정", "강", "윤", "장", "임", "한",
                "오", "서", "신", "권", "황", "안", "송", "류", "전", "홍"]

DEPARTMENTS = [
    "품질보증팀", "생산관리팀", "금형생산팀", "자동화기술팀", "안전보건팀",
    "개발팀", "구매팀", "재경팀", "IT전략팀", "ESG경영팀", "인사팀",
    "해외지원팀", "영업팀", "물류팀", "설비보전팀",
]

DEPT_ALIASES = [
    "품보팀", "생관팀", "금형팀", "자동화팀", "안보팀", "QA", "HR",
    "IT팀", "ESG팀", "구매", "재경", "영업", "물류",
]

POSITIONS = ["사원", "대리", "과장", "차장", "부장", "팀장"]

DOC_TYPES = [
    "8D 보고서", "ECN", "PPAP", "회의록", "이메일", "공문",
    "품질문제 개선대책서", "안전 인시던트 리포트", "납입용기 규격 설정서",
]

TERMS = [
    "SPC", "Cpk", "PPAP", "APQP", "8D", "FMEA", "MSA", "ECN",
    "EWP", "CCH", "OBC", "DASH COMPL", "프리프레그", "CFRP",
    "IATF", "ISO", "REACH", "IRA", "USMCA", "OSHA",
    "금형", "프레스", "용접", "사출", "CNC", "로봇",
    "서보", "유압", "너겟", "Cpk", "관리도", "불량률",
]

REGULATIONS = [
    "REACH", "IRA", "USMCA", "OSHA", "EPA", "산안법", "CBAM",
    "관세", "EU 규제", "미국 규제", "환경 규제", "안전 기준",
]


# ──────────────────────────────────────────────
# 의도별 템플릿
# ──────────────────────────────────────────────

INTENT_TEMPLATES = {
    "employee_lookup": [
        "{name} {position} 연락처 알려줘",
        "{name} {position} 이메일 뭐야",
        "{name} {position} 전화번호",
        "{department} 팀장이 누구야",
        "{department} 사람들 목록",
        "{department} 소속 인원 보여줘",
        "{department} {position} 찾아줘",
        "내선번호 {ext}번이 누구야",
        "{dept_alias} 팀원들 누구야",
        "{name} {position} 내선번호",
        "{department} 조직도 보여줘",
        "조직도 알려줘",
        "{department} 구성원 현황",
        "{dept_alias} 멤버",
        "{name} {position} 부서가 어디야",
    ],
    "company_info": [
        "아진산업 연혁 알려줘",
        "회사 매출이 얼마야",
        "해외법인 어디에 있어",
        "JOON INC가 뭐야",
        "HMGMA 관련 정보",
        "회사 복지 제도 알려줘",
        "조지아 공장 정보",
        "사장님이 누구야",
        "아진산업 설립연도",
        "경산 본사 위치",
        "{term} 용어가 뭐야",
        "{term} 뜻 알려줘",
        "{term} 설명해줘",
        "신입사원 교육 일정",
        "복지 혜택 뭐가 있어",
    ],
    "document_search": [
        "{doc_type} 양식 찾아줘",
        "{doc_type} 템플릿 어디 있어",
        "{doc_type} 관련 문서",
        "{term} 관련 문서 검색해줘",
        "{department} 관련 문서 보여줘",
        "품질 보고서 찾아줘",
        "최근 작성된 {doc_type} 보여줘",
        "{term} 절차서 어디 있어",
        "PPAP 서류 검색",
        "8D 보고서 양식",
    ],
    "document_compose": [
        "{doc_type} 작성해줘",
        "{name} {position}에게 이메일 써줘",
        "회의록 만들어줘",
        "보고서 초안 작성해줘",
        "{department}에 보낼 공문 써줘",
        "8D 보고서 작성",
        "ECN 문서 만들어줘",
        "{name}에게 보낼 메일 작성",
        "품질 개선대책서 작성해줘",
        "{doc_type} 양식으로 문서 생성",
        "이메일 초안 써줘",
        "납기 지연 사과 이메일 작성",
    ],
    "regulation_query": [
        "{regulation} 규제 현황 알려줘",
        "관세 25% 영향 분석",
        "{regulation} 언제부터 적용이야",
        "미국 규제 현황",
        "EU REACH 준수 사항",
        "{regulation} 관련 공장 영향",
        "산안법 최근 변경사항",
        "IRA 세액공제 조건",
        "환경 규제 모니터링",
        "CBAM 탄소국경조정 현황",
        "{regulation} 대응 방안",
        "규제 위반 시 과징금",
    ],
}


# ──────────────────────────────────────────────
# 텍스트 변형(Augmentation)
# ──────────────────────────────────────────────

def augment_text(text: str) -> str:
    """텍스트 변형 (오타/줄임말/구어체)"""
    augmented = text

    # 1) 랜덤 조사 생략 (20% 확률)
    if random.random() < 0.2:
        for particle in ["을", "를", "이", "가", "에", "의", "에서", "으로", "로"]:
            if random.random() < 0.3:
                augmented = augmented.replace(particle, "", 1)

    # 2) 어미 변형 (30% 확률)
    if random.random() < 0.3:
        replacements = {
            "알려줘": random.choice(["알려주세요", "알려줘요", "알려 줘", "알려조"]),
            "보여줘": random.choice(["보여주세요", "보여 줘", "보여줘요"]),
            "찾아줘": random.choice(["찾아주세요", "찾아 줘", "찾아줘요"]),
            "써줘": random.choice(["써주세요", "써 줘", "작성해줘"]),
            "작성해줘": random.choice(["작성해주세요", "작성해 줘", "만들어줘"]),
            "뭐야": random.choice(["뭐야?", "뭐에요?", "뭔가요", "뭐임"]),
        }
        for old, new in replacements.items():
            if old in augmented:
                augmented = augmented.replace(old, new, 1)
                break

    # 3) 물음표/마침표 랜덤 (30% 확률)
    if random.random() < 0.3:
        if not augmented.endswith(("?", ".", "!")):
            augmented += random.choice(["?", "", ".", ""])

    # 4) 띄어쓰기 오류 (15% 확률)
    if random.random() < 0.15:
        words = augmented.split()
        if len(words) >= 3:
            idx = random.randint(0, len(words) - 2)
            words[idx] = words[idx] + words[idx + 1]
            words.pop(idx + 1)
            augmented = " ".join(words)

    return augmented


def generate_training_data(n_per_intent: int = 300) -> List[Dict]:
    """의도별 합성 학습 데이터 생성"""
    data = []

    for intent, templates in INTENT_TEMPLATES.items():
        for _ in range(n_per_intent):
            template = random.choice(templates)

            # 슬롯 채우기
            filled = template
            filled = filled.replace("{name}", random.choice(PERSON_NAMES))
            filled = filled.replace("{position}", random.choice(POSITIONS))
            filled = filled.replace("{department}", random.choice(DEPARTMENTS))
            filled = filled.replace("{dept_alias}", random.choice(DEPT_ALIASES))
            filled = filled.replace("{doc_type}", random.choice(DOC_TYPES))
            filled = filled.replace("{term}", random.choice(TERMS))
            filled = filled.replace("{regulation}", random.choice(REGULATIONS))
            filled = filled.replace("{ext}", str(random.randint(1001, 9999)))

            # 변형 적용 (50% 확률)
            if random.random() < 0.5:
                filled = augment_text(filled)

            data.append({"text": filled, "intent": intent})

    # 셔플
    random.shuffle(data)

    return data


def save_training_data(data: List[Dict], output_path: str = None):
    """CSV로 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = str(OUTPUT_DIR / "intent_training_data.csv")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "intent"])
        writer.writeheader()
        writer.writerows(data)

    intent_counts = {}
    for d in data:
        intent_counts[d["intent"]] = intent_counts.get(d["intent"], 0) + 1

    print(f"학습 데이터 생성: {len(data)}건 -> {output_path}")
    for intent, count in sorted(intent_counts.items()):
        print(f"  {intent}: {count}건")


if __name__ == "__main__":
    print("의도 분류 ML 합성 데이터 생성 시작...")
    data = generate_training_data(n_per_intent=300)
    save_training_data(data)
    print("완료!")
