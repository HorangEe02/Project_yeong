"""가상 인원 데이터 생성 스크립트

⚠️ 주의: 이 스크립트가 생성하는 모든 인원 데이터는 시연용 가상 데이터입니다.
실제 아진산업 임직원과는 일체 관련이 없습니다.
"""

import random
from datetime import date, timedelta
from pathlib import Path

from features.search.employee.database import EmployeeDatabase, POSITION_HIERARCHY

# AJIN_ORGANIZATION_REFERENCE.md 기반 실제 조직 구조
# 329명 기준 (아진산업 실제 사원 수 반영)
# plant 값: "경산 본사" = 본사 고정, "mixed" = 생산현장 분산, "mixed_office" = 사무직 분산
ORGANIZATION = {
    "재경본부": {
        "재무팀": {"size": 8, "plant": "mixed_office"},
        "회계팀": {"size": 9, "plant": "mixed_office"},
        "IT전략팀": {"size": 10, "plant": "mixed_office"},
        "원가기획팀": {"size": 7, "plant": "경산 본사"},
    },
    "관리본부": {
        "총무인사팀": {"size": 14, "plant": "mixed_office"},
        "품질경영팀": {"size": 10, "plant": "mixed"},
        "ESG경영팀": {"size": 6, "plant": "경산 본사"},
        "기술교육원": {"size": 8, "plant": "mixed_office"},
    },
    "구매본부": {
        "구매팀": {"size": 12, "plant": "경산 본사"},
        "해외지원팀": {"size": 8, "plant": "경산 본사"},
        "상생협력팀": {"size": 6, "plant": "경산 본사"},
    },
    "생산본부": {
        "생산관리팀": {"size": 20, "plant": "mixed"},
        "안전보건팀": {"size": 12, "plant": "mixed"},
        "품질보증팀": {"size": 22, "plant": "mixed"},
        "영업팀": {"size": 10, "plant": "경산 본사"},
        "자재관리팀": {"size": 8, "plant": "mixed"},
    },
    "개발본부": {
        "기술영업팀": {"size": 9, "plant": "경산 본사"},
        "부품개발팀": {"size": 14, "plant": "mixed_office"},
        "금형생산팀": {"size": 16, "plant": "mixed"},
    },
    "생산기술본부": {
        "자동화기술팀": {"size": 11, "plant": "mixed"},
        "FA사업팀": {"size": 8, "plant": "경산 본사"},
        "플랜트사업팀": {"size": 7, "plant": "경산 본사"},
        "제품설계팀": {"size": 11, "plant": "경산 본사"},
        "공법계획팀": {"size": 9, "plant": "mixed"},
        "생산기술팀": {"size": 14, "plant": "mixed"},
        "용기운영팀": {"size": 7, "plant": "mixed"},
        "비전연구팀": {"size": 8, "plant": "경산 본사"},
    },
    "기술연구소": {
        "바디선행개발팀": {"size": 11, "plant": "경산 본사"},
        "전장선행개발팀": {"size": 9, "plant": "경산 본사"},
    },
}

INDEPENDENT = {
    "내부감사팀": {"size": 4, "division": "(독립)", "plant": "경산 본사"},
}

EXTENSION_RANGES = {
    "(독립)": (1000, 1099),
    "재경본부": (1100, 1399),
    "관리본부": (2000, 2399),
    "구매본부": (3000, 3299),
    "생산본부": (4000, 4599),
    "개발본부": (5000, 5399),
    "생산기술본부": (6000, 6599),
    "기술연구소": (7000, 7299),
}

# 현장 부서(생산/품질/안전 등)의 공장 분산 비율
# plants.json 기준: 경산 본사(450명), 경산 제2(150명), 경주 구어(200명) → 비율 반영
MIXED_PLANTS_PRODUCTION = [
    "경산 본사", "경산 본사", "경산 본사",   # 45%
    "경산 제2공장", "경산 제2공장",           # 20%
    "경주 구어공장", "경주 구어공장",         # 20%
    "아진카인텍 (경주)",                     # 10%
    "대우전자부품 (정읍)",                   # 5%
]

# 사무직 부서 — 본사 + 일부 계열사
MIXED_PLANTS_OFFICE = [
    "경산 본사", "경산 본사", "경산 본사", "경산 본사",  # 80%
    "아진금형텍 (경산)",                               # 20%
]

PLANT_ID_MAP = {
    # 자사 공장
    "경산 본사": "PLANT-KS-HQ",
    "경산 제2공장": "PLANT-KS-2",
    "경주 구어공장": "PLANT-GJ",
    # 국내 계열사
    "아진카인텍 (경주)": "PLANT-GJ-KAINTECH",
    "대우전자부품 (정읍)": "PLANT-JJ",
    "아진금형텍 (경산)": "PLANT-KS-MOLDTECH",
    # 해외법인
    "아진실업 (중국 상해)": "SUB-CN-SH",
    "강소아진 (중국 염성)": "SUB-CN-YC",
    "동풍아진 (중국)": "SUB-CN-DF",
    "아진 USA (앨라배마)": "SUB-US-AJIN",
    "우신 USA": "SUB-US-WOOSHIN",
    "대우전자 베트남": "SUB-VN",
}

FAMILY_NAMES = [
    ("김", "Kim"), ("이", "Lee"), ("박", "Park"), ("최", "Choi"),
    ("정", "Jung"), ("강", "Kang"), ("조", "Cho"), ("윤", "Yoon"),
    ("장", "Jang"), ("임", "Lim"), ("한", "Han"), ("오", "Oh"),
    ("서", "Seo"), ("신", "Shin"), ("권", "Kwon"), ("황", "Hwang"),
    ("안", "Ahn"), ("송", "Song"), ("류", "Ryu"), ("홍", "Hong"),
]

MALE_GIVEN_NAMES = [
    ("민수", "Minsu"), ("준혁", "Junhyuk"), ("성호", "Sungho"), ("재현", "Jaehyun"),
    ("동현", "Donghyun"), ("지훈", "Jihoon"), ("영수", "Youngsu"), ("태영", "Taeyoung"),
    ("현우", "Hyunwoo"), ("승민", "Seungmin"), ("정훈", "Junghoon"), ("기현", "Kihyun"),
    ("상우", "Sangwoo"), ("진호", "Jinho"), ("대호", "Daeho"), ("건우", "Gunwoo"),
    ("시우", "Siwoo"), ("우진", "Woojin"), ("하준", "Hajun"), ("도윤", "Doyoon"),
    ("서준", "Seojun"), ("예준", "Yejun"), ("시윤", "Siyoon"), ("주원", "Juwon"),
    ("지호", "Jiho"), ("준서", "Junseo"), ("민재", "Minjae"), ("현준", "Hyunjun"),
    ("유찬", "Yuchan"), ("도현", "Dohyun"), ("수호", "Suho"), ("은호", "Eunho"),
    ("태민", "Taemin"), ("정우", "Jungwoo"), ("찬영", "Chanyoung"), ("재윤", "Jaeyoon"),
    ("한결", "Hangyul"), ("선호", "Sunho"), ("윤호", "Yoonho"), ("경민", "Kyungmin"),
    ("세현", "Sehyun"), ("원석", "Wonseok"), ("용준", "Yongjun"), ("병호", "Byungho"),
    ("인성", "Insung"), ("태준", "Taejun"), ("명진", "Myungjin"), ("창수", "Changsu"),
]

FEMALE_GIVEN_NAMES = [
    ("수진", "Sujin"), ("지은", "Jieun"), ("미영", "Miyoung"), ("혜진", "Hyejin"),
    ("은지", "Eunji"), ("유진", "Yujin"), ("서연", "Seoyeon"), ("민지", "Minji"),
    ("하은", "Haeun"), ("지현", "Jihyun"), ("예은", "Yeeun"), ("수빈", "Subin"),
    ("소연", "Soyeon"), ("지영", "Jiyoung"), ("현정", "Hyunjeong"), ("은서", "Eunseo"),
    ("채원", "Chaewon"), ("나은", "Naeun"), ("시현", "Sihyun"), ("다은", "Daeun"),
    ("윤아", "Yoona"), ("보라", "Bora"), ("세희", "Sehee"), ("주하", "Juha"),
]


def generate_employees() -> list[dict]:
    """가상 인원 데이터를 생성한다."""
    random.seed(42)  # 재현성
    employees = []
    emp_counter = 0
    used_extensions: set[str] = set()
    used_names: set[str] = set()

    def make_employee(division, department, position, position_level, plant, is_leader=False):
        nonlocal emp_counter
        emp_counter += 1

        while True:
            gender = random.choice(["M", "M", "M", "F"])
            family = random.choice(FAMILY_NAMES)
            given = random.choice(MALE_GIVEN_NAMES if gender == "M" else FEMALE_GIVEN_NAMES)
            full_name = family[0] + given[0]
            if full_name not in used_names:
                used_names.add(full_name)
                break

        name_en = f"{given[1]} {family[1]}"

        ext_range = EXTENSION_RANGES.get(division, (8000, 8999))
        while True:
            ext = str(random.randint(ext_range[0], ext_range[1]))
            if ext not in used_extensions:
                used_extensions.add(ext)
                break

        years_offset = {
            0: (0, 1), 1: (0, 3), 2: (1, 5), 3: (3, 8), 4: (6, 12),
            5: (10, 16), 6: (12, 20), 7: (15, 22), 8: (18, 25),
            9: (20, 28), 10: (22, 30),
        }
        yr_min, yr_max = years_offset.get(position_level, (0, 5))
        days_ago = random.randint(yr_min * 365, yr_max * 365)
        hire_date = (date.today() - timedelta(days=days_ago)).isoformat()

        email = f"{family[1].lower()}.{given[1].lower()}@ajin.co.kr"
        phone = f"010-{random.randint(1000,9999)}-{random.randint(1000,9999)}"

        return {
            "employee_id": f"EMP-{emp_counter:04d}",
            "name": full_name, "name_en": name_en, "gender": gender,
            "position": position, "position_level": position_level,
            "division": division, "department": department,
            "email": email, "phone": phone, "extension": ext,
            "plant": plant, "plant_id": PLANT_ID_MAP.get(plant, ""),
            "hire_date": hire_date, "is_active": 1,
            "is_team_leader": 1 if is_leader else 0,
        }

    # 직급 분포 비율 (제조업 중견기업 기준)
    # 인턴 3%, 사원 30%, 주임 12%, 대리 18%, 과장 15%, 차장 10%, (부장은 팀장으로 별도)
    def _make_position_pool(remaining: int) -> list[str]:
        pool = (
            ["인턴"] * max(1, int(remaining * 0.03))
            + ["사원"] * int(remaining * 0.30)
            + ["주임"] * int(remaining * 0.12)
            + ["대리"] * int(remaining * 0.18)
            + ["과장"] * int(remaining * 0.15)
            + ["차장"] * int(remaining * 0.10)
        )
        while len(pool) < remaining:
            pool.append(random.choice(["사원", "사원", "주임", "대리"]))
        random.shuffle(pool)
        return pool[:remaining]

    for division, teams in ORGANIZATION.items():
        for dept_name, dept_info in teams.items():
            size = dept_info["size"]
            base_plant = dept_info["plant"]

            leader_plant = "경산 본사" if base_plant in ("mixed", "mixed_office") else base_plant
            employees.append(make_employee(division, dept_name, "부장", 6, leader_plant, is_leader=True))

            remaining = size - 1
            position_pool = _make_position_pool(remaining)

            for pos in position_pool[:remaining]:
                if base_plant == "mixed":
                    plant = random.choice(MIXED_PLANTS_PRODUCTION)
                elif base_plant == "mixed_office":
                    plant = random.choice(MIXED_PLANTS_OFFICE)
                else:
                    plant = base_plant
                employees.append(make_employee(division, dept_name, pos, POSITION_HIERARCHY[pos], plant))

    # 독립 부서
    for dept_name, info in INDEPENDENT.items():
        employees.append(make_employee(info["division"], dept_name, "부장", 6, info["plant"], is_leader=True))
        for _ in range(info["size"] - 1):
            pos = random.choice(["과장", "대리", "주임"])
            employees.append(make_employee(info["division"], dept_name, pos, POSITION_HIERARCHY[pos], info["plant"]))

    # 임원진 (본부장급: 이사/상무/전무) — 각 본부에 1명씩
    exec_positions = [
        ("재경본부", "상무"), ("관리본부", "이사"), ("구매본부", "이사"),
        ("생산본부", "전무"), ("개발본부", "상무"), ("생산기술본부", "전무"),
        ("기술연구소", "이사"),
    ]
    for div, pos in exec_positions:
        first_team = list(ORGANIZATION[div].keys())[0]
        employees.append(make_employee(
            div, first_team, pos, POSITION_HIERARCHY[pos], "경산 본사",
        ))

    # 해외법인 주재원 (해외지원팀 소속으로 각 법인에 배치)
    overseas_sites = [
        ("아진실업 (중국 상해)", 3),
        ("강소아진 (중국 염성)", 2),
        ("동풍아진 (중국)", 2),
        ("아진 USA (앨라배마)", 3),
        ("우신 USA", 2),
        ("대우전자 베트남", 2),
    ]
    for site, count in overseas_sites:
        for i in range(count):
            pos = "과장" if i == 0 else random.choice(["대리", "주임", "사원"])
            employees.append(make_employee(
                "구매본부", "해외지원팀", pos, POSITION_HIERARCHY[pos], site,
            ))

    return employees


def seed_database(db_path: str | Path | None = None) -> int:
    """가상 인원 데이터를 DB에 저장한다."""
    db = EmployeeDatabase(db_path)
    db.conn.execute("DELETE FROM employees")
    db.conn.commit()

    employees = generate_employees()

    for emp in employees:
        db.conn.execute(
            """INSERT INTO employees
               (employee_id, name, name_en, gender, position, position_level,
                division, department, email, phone, extension, plant, plant_id,
                hire_date, is_active, is_team_leader)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (emp["employee_id"], emp["name"], emp["name_en"], emp["gender"],
             emp["position"], emp["position_level"], emp["division"],
             emp["department"], emp["email"], emp["phone"], emp["extension"],
             emp["plant"], emp.get("plant_id", ""), emp["hire_date"],
             emp["is_active"], emp["is_team_leader"]),
        )

    db.conn.commit()
    total = db.get_total_headcount()
    print(f"[OK] 가상 인원 데이터 생성 완료: {total}명")

    for div in db.get_division_headcount():
        print(f"  {div['division']}: {div['headcount']}명")

    db.close()
    return total


def seed_overseas_assignments():
    """v1.6: 기존 사원 중 일부에 해외파견 정보를 부여한다."""
    db = EmployeeDatabase()

    # 해외파견 대상 부서 → 파견지 매핑
    assignments = [
        # (부서, 직급, 파견지, 언어)
        ("기술영업팀", "과장", "Georgia (JOON INC)", "영어,한국어"),
        ("기술영업팀", "대리", "Georgia (JOON INC)", "영어,한국어"),
        ("기술영업팀", "차장", "Alabama (AJIN USA)", "영어,한국어"),
        ("해외지원팀", "과장", "Georgia (JOON INC)", "영어,한국어"),
        ("해외지원팀", "대리", "Georgia (JOON INC)", "영어,한국어"),
        ("해외지원팀", "차장", "Shanghai", "중국어,한국어"),
        ("해외지원팀", "대리", "Yancheng", "중국어,한국어"),
        ("품질보증팀", "과장", "Georgia (JOON INC)", "영어,한국어"),
        ("품질보증팀", "대리", "Alabama (AJIN USA)", "영어,한국어"),
        ("품질보증팀", "주임", "Vietnam", "영어,한국어"),
        ("구매팀", "과장", "Shanghai", "중국어,한국어"),
        ("구매팀", "대리", "Yancheng", "중국어,한국어"),
        ("생산기술팀", "과장", "Georgia (JOON INC)", "영어,한국어"),
        ("생산기술팀", "대리", "Alabama (AJIN USA)", "영어,한국어"),
        ("전장선행개발팀", "대리", "Georgia (JOON INC)", "영어,한국어"),
    ]

    updated = 0
    for dept, pos, overseas, langs in assignments:
        # 해당 부서+직급에서 1명 찾아 업데이트
        row = db.conn.execute(
            "SELECT employee_id FROM employees WHERE department=? AND position=? AND overseas_assignment IS NULL LIMIT 1",
            (dept, pos),
        ).fetchone()
        if row:
            db.conn.execute(
                "UPDATE employees SET overseas_assignment=?, language_skills=? WHERE employee_id=?",
                (overseas, langs, row["employee_id"]),
            )
            updated += 1

    db.conn.commit()
    print(f"[OK] 해외파견 데이터 업데이트: {updated}명")
    db.close()
    return updated


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    seed_database()
    seed_overseas_assignments()
