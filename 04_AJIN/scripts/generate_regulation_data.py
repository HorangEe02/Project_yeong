"""
규제 리스크 분류 ML 학습용 합성 데이터 생성기
- 기존 9건 시나리오를 템플릿으로 확장
- 심각도(HIGH/MEDIUM/LOW) 라벨 포함
- 규제 유형별 특성 반영
"""

import random
import csv
from pathlib import Path
from typing import List, Dict


OUTPUT_DIR = Path("data/regulation_ml")

# 규제 유형 × 심각도 템플릿
REGULATION_TEMPLATES = {
    "HIGH": [
        "{chemical} 화합물 사용 전면 금지 — 즉시 대체물질 전환 필요",
        "{product} 수출 금지 조치 발동 — 관세 {rate}% 부과 확정",
        "{product} 리콜 명령 — 안전 기준 위반으로 전량 회수",
        "{standard} 인증 즉시 취소 위험 — 기한 내 시정 미이행 시",
        "작업장 조업 중단 명령 — {safety} 기준 중대 위반",
        "OEM 납품 중단 통보 — {quality} 기준 미달",
        "형사 처벌 대상 — {law} 위반으로 대표이사 고발 가능",
        "{country} 시장 진입 불가 — 필수 인가 미취득",
    ],
    "MEDIUM": [
        "{standard} 규제 기준 강화 — {deadline}까지 대응 필요",
        "{chemical} 사용 제한 강화 — 허용 농도 {limit} 이하로 변경",
        "{product} 추가 시험 요구 — 신규 안전기준 적용",
        "보고 의무 신설 — {report} 분기별 제출 의무화",
        "{country} 관세율 조정 — 기존 {old_rate}% → {new_rate}%",
        "모니터링 강화 대상 지정 — {area} 분야 정기 감사",
        "{safety} 기준 변경 — 기존 설비 업그레이드 필요",
        "공급망 실사 의무화 — {scope} 범위 확대",
    ],
    "LOW": [
        "{standard} 가이드라인 개정 — 자발적 적용 권고",
        "{country} 인센티브 프로그램 신설 — 세액공제 {credit} 적용 가능",
        "산업 동향 보고서 — {trend} 분야 향후 규제 예고",
        "단계적 적용 예정 — {timeline}년부터 본격 시행",
        "자발적 준수 프로그램 — 참여 기업 인센티브 제공",
        "업계 협의체 구성 — {topic} 표준 제정 논의 시작",
        "시범 사업 모집 — {program} 참여 기업 우대",
        "교육 의무 신설 — {hours}시간 연간 교육 이수 권고",
    ],
}

# 슬롯 채우기 데이터
CHEMICALS = ["6가 크롬", "납", "카드뮴", "수은", "PFAS", "프탈레이트", "벤젠", "아스베스트"]
PRODUCTS = ["EWP", "CCH", "OBC", "DASH COMPL", "범퍼빔", "서브프레임", "배터리 케이스"]
STANDARDS = ["IATF 16949", "ISO 14001", "ISO 45001", "REACH", "RoHS", "CBAM", "IRA"]
SAFETY = ["소음", "분진", "유해화학물질", "기계 안전", "전기 안전", "화재", "고온"]
QUALITY = ["Cpk", "불량률", "공정능력", "측정시스템", "검사 기준"]
COUNTRIES = ["EU", "미국", "중국", "한국", "베트남"]
LAWS = ["산업안전보건법", "화학물질관리법", "환경보전법", "품질경영법", "OSHA"]

DEPARTMENTS_BY_SEVERITY = {
    "HIGH": [
        ["품질보증팀", "구매팀"], ["안전보건팀", "생산본부"],
        ["개발본부", "품질보증팀"], ["ESG경영팀", "재경팀"],
        ["해외지원팀", "영업팀"],
    ],
    "MEDIUM": [
        ["품질보증팀"], ["안전보건팀"], ["개발본부"],
        ["구매팀"], ["ESG경영팀"], ["해외지원팀"],
    ],
    "LOW": [
        ["ESG경영팀"], ["품질보증팀"], ["개발본부"], ["해외지원팀"],
    ],
}


def generate_training_data(n_per_severity: int = 150) -> List[Dict]:
    """심각도별 합성 규제 텍스트 생성"""
    data = []

    for severity, templates in REGULATION_TEMPLATES.items():
        for _ in range(n_per_severity):
            template = random.choice(templates)

            filled = template
            filled = filled.replace("{chemical}", random.choice(CHEMICALS))
            filled = filled.replace("{product}", random.choice(PRODUCTS))
            filled = filled.replace("{standard}", random.choice(STANDARDS))
            filled = filled.replace("{safety}", random.choice(SAFETY))
            filled = filled.replace("{quality}", random.choice(QUALITY))
            filled = filled.replace("{country}", random.choice(COUNTRIES))
            filled = filled.replace("{law}", random.choice(LAWS))
            filled = filled.replace("{rate}", str(random.choice([10, 15, 20, 25, 30, 40])))
            filled = filled.replace("{old_rate}", str(random.choice([5, 8, 10])))
            filled = filled.replace("{new_rate}", str(random.choice([15, 20, 25])))
            filled = filled.replace("{limit}", f"{random.choice([0.1, 0.5, 1.0, 5.0])}ppm")
            filled = filled.replace("{deadline}", f"2026-{random.randint(6,12):02d}")
            filled = filled.replace("{credit}", f"${random.choice([3000, 5000, 7500]):,}")
            filled = filled.replace("{timeline}", str(random.choice([2027, 2028, 2029, 2030])))
            filled = filled.replace("{report}", random.choice(["ESG", "배출량", "유해물질", "안전"]))
            filled = filled.replace("{area}", random.choice(["환경", "안전", "품질", "무역"]))
            filled = filled.replace("{scope}", random.choice(["1차 협력사", "전체 공급망", "해외법인"]))
            filled = filled.replace("{topic}", random.choice(["탄소중립", "재활용", "안전"]))
            filled = filled.replace("{program}", random.choice(["친환경", "스마트팩토리", "ESG"]))
            filled = filled.replace("{trend}", random.choice(["탄소규제", "EV 안전", "순환경제"]))
            filled = filled.replace("{hours}", str(random.choice([8, 16, 24, 40])))

            depts = random.choice(DEPARTMENTS_BY_SEVERITY[severity])

            data.append({
                "text": filled,
                "severity": severity,
                "departments": ",".join(depts),
            })

    random.shuffle(data)
    return data


def save_training_data(data: List[Dict]):
    """CSV 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "regulation_training_data.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "severity", "departments"])
        writer.writeheader()
        writer.writerows(data)

    counts = {}
    for d in data:
        counts[d["severity"]] = counts.get(d["severity"], 0) + 1
    print(f"학습 데이터: {len(data)}건 → {output_path}")
    for sev, cnt in sorted(counts.items()):
        print(f"  {sev}: {cnt}건")


if __name__ == "__main__":
    print("규제 리스크 ML 합성 데이터 생성...")
    data = generate_training_data(n_per_severity=150)
    save_training_data(data)
    print("완료!")
