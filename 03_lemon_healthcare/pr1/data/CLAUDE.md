# data/CLAUDE.md — 데이터 작업 컨텍스트 (Tier 2)

> 이 문서는 **데이터(`data/`) 작업 시 추가로 읽어야 하는 컨텍스트**입니다.  
> KDRIs 디지털화, 식약처 API 통합, 가명정보 처리 등 모든 데이터 관련 작업의 표준 절차.

---

## 🎯 data/ 폴더의 역할

이 폴더는 **정적·반정적 데이터**를 보관합니다:

- KDRIs 영양 기준 룩업 테이블
- 식약처 건강기능식품 원료 정리표
- 농진청 식품성분 표준 데이터
- 한국 음식 카테고리 정의
- 만성질환 코드 매핑

**보관하지 않는 것**:
- ❌ 사용자 개인정보 (DB에만)
- ❌ 영양제·식단 사진 (Object Storage에)
- ❌ 큰 데이터셋 (Git LFS 또는 외부 저장)

---

## 📂 data/ 폴더 구조

```
data/
├── CLAUDE.md                    ← 이 파일
├── README.md                    # 사용자 노출용 출처·라이선스
│
├── kdris/                       # KDRIs 룩업 테이블
│   ├── kdris_2020.csv           # 메인 룩업 (30종 영양소)
│   ├── kdris_metadata.json      # 컬럼 정의·단위
│   └── kdris_special.csv        # 임신부·수유부·유아 별도
│
├── mfds/                        # 식약처 데이터
│   ├── functional_ingredients.csv   # 건강기능식품 인정 원료
│   ├── functional_claims.csv        # 식약처 인정 기능성 표시
│   └── unit_conversions.json        # 단위 환산 (mg ↔ μg ↔ IU)
│
├── rda/                         # 농진청 식품성분
│   ├── korean_foods.csv         # 한식 영양 정보
│   └── traditional_foods.csv    # 전통 식품 (김치·장류·떡류)
│
├── reference/                   # 참조 데이터
│   ├── disease_codes.json       # 만성질환 코드 매핑
│   ├── nutrient_codes.json      # 영양소 표준 코드
│   └── allergens.json           # 알레르기 유발 성분
│
└── sample/                      # 테스트용 샘플 (작은 익명 데이터)
    ├── supplement_labels/       # 영양제 라벨 사진 (저작권 확인 필수)
    └── meal_examples.json       # 식단 입력 예시
```

> ⚠️ **`data/raw/` 와 `data/private/` 는 .gitignore 처리** — 원본·민감 데이터는 절대 커밋 금지.

---

## 🔥 데이터 작업 절대 규칙

### Rule 1. 모든 데이터에 출처·버전·라이선스 명시

새 데이터 파일을 추가할 때마다 함께 메타 정보 작성:

```yaml
# data/kdris/kdris_metadata.json 예시
{
  "name": "한국인 영양소 섭취기준",
  "version": "KDRIs-2020",
  "source_url": "https://www.kns.or.kr",
  "publisher": "한국영양학회 + 보건복지부",
  "license": "공공저작물 자유이용",
  "license_url": "https://www.kogl.or.kr/",
  "downloaded_at": "2026-05-03",
  "downloaded_by": "TBD",
  "format": "CSV",
  "encoding": "UTF-8",
  "row_count": 360,
  "column_definitions": {
    "code": "영양소 표준 코드 (e.g., vitamin_c_mg)",
    "name_ko": "한국어 영양소명",
    "name_en": "영어 영양소명",
    "unit": "단위 (mg, μg, g, IU)",
    "sex": "성별 (male/female/all)",
    "age_min": "연령 범위 시작 (만 나이)",
    "age_max": "연령 범위 끝",
    "rda": "권장 섭취량 (Recommended Dietary Allowance)",
    "ai": "충분 섭취량 (Adequate Intake)",
    "ear": "평균 필요량 (Estimated Average Requirement)",
    "ul": "상한 섭취량 (Upper Intake Level)"
  }
}
```

### Rule 2. CSV는 UTF-8 + BOM 제거 + LF 라인 종결

```bash
# 인코딩 확인
file -i data/kdris/kdris_2020.csv
# 정상: text/csv; charset=utf-8

# BOM 제거
sed -i '1s/^\xEF\xBB\xBF//' data/kdris/kdris_2020.csv

# CRLF → LF (Windows에서 만든 경우)
dos2unix data/kdris/kdris_2020.csv
```

### Rule 3. 표준 영양소 코드 사용

영양소는 `data/reference/nutrient_codes.json` 의 표준 코드만 사용:

```json
{
  "vitamin_c_mg": {"name_ko": "비타민 C", "name_en": "Vitamin C", "unit": "mg"},
  "vitamin_d_ug": {"name_ko": "비타민 D", "name_en": "Vitamin D", "unit": "μg"},
  "vitamin_d_iu": {"name_ko": "비타민 D", "name_en": "Vitamin D", "unit": "IU"},
  "calcium_mg": {"name_ko": "칼슘", "name_en": "Calcium", "unit": "mg"},
  "iron_mg": {"name_ko": "철분", "name_en": "Iron", "unit": "mg"},
  ...
}
```

> 코드 명명 규칙: `{영양소}_{단위}` (snake_case, 영어, 단위 포함)

### Rule 4. 만성질환 코드 표준

```json
// data/reference/disease_codes.json
{
  "diabetes": {
    "name_ko": "당뇨병",
    "name_en": "Diabetes Mellitus",
    "icd10": "E11",
    "weight_v4": 0.10
  },
  "hypertension": {
    "name_ko": "고혈압",
    "name_en": "Hypertension",
    "icd10": "I10",
    "weight_v4": 0.10
  },
  "cardiovascular": {
    "name_ko": "심혈관질환",
    "name_en": "Cardiovascular Disease",
    "icd10": "I50",
    "weight_v4": 0.15
  },
  "joint": {
    "name_ko": "관절질환",
    "name_en": "Joint Disease",
    "icd10": "M19",
    "weight_v4": 0.15
  },
  "respiratory": {
    "name_ko": "호흡기질환",
    "name_en": "Respiratory Disease",
    "icd10": "J44",
    "weight_v4": 0.10
  }
}
```

### Rule 5. 단위 표준 + 환산 명시

영양제 라벨에는 다양한 단위가 등장 (mg, μg, IU, g, 정, 캡슐). 표준 단위로 변환하는 룰을 `data/mfds/unit_conversions.json` 에 정의:

```json
{
  "vitamin_a": {
    "1_iu": "0.3 μg RAE",
    "1_ug_rae": "3.33 IU"
  },
  "vitamin_d": {
    "1_iu": "0.025 μg",
    "1_ug": "40 IU"
  },
  "vitamin_e": {
    "1_iu": "0.67 mg α-TE",
    "1_mg_ate": "1.49 IU"
  }
}
```

---

## 🛡 가명정보·민감정보 처리 (필수 준수)

> 의료 도메인 프로젝트의 **가장 위험한 영역**. 작업 전 반드시 [docs/10-compliance-checklist.md §5](../docs/10-compliance-checklist.md) 정독.

### 가명처리 표준 절차

#### Step 1. 직접 식별자 제거

```python
"""가명처리 헬퍼."""

from __future__ import annotations

import hashlib
from typing import Any


DIRECT_IDENTIFIERS: frozenset[str] = frozenset({
    "name",
    "phone",
    "email",
    "address",
    "ip_address",
    "ssn",          # 주민번호
    "passport_no",
})
"""직접 식별자 — 가명처리 시 제거."""


def remove_direct_identifiers(record: dict[str, Any]) -> dict[str, Any]:
    """레코드에서 직접 식별자를 제거한다.

    Args:
        record: 사용자 데이터 레코드.

    Returns:
        직접 식별자가 제거된 새 딕셔너리.

    Examples:
        >>> remove_direct_identifiers(
        ...     {"name": "홍길동", "age": 50, "email": "x@y.com"}
        ... )
        {'age': 50}
    """
    return {k: v for k, v in record.items() if k not in DIRECT_IDENTIFIERS}
```

#### Step 2. 간접 식별자 일반화

| 원본 | 일반화 |
|------|-------|
| 생년월일 (1972-03-15) | 연령대 (50대) |
| 주소 (서울 강남구 역삼동 123) | 시/도 (서울) |
| 정확한 키 (172.5cm) | 5cm 단위 (170~175) |
| 정확한 체중 (68.3kg) | 5kg 단위 (65~70) |

```python
def generalize_age(birth_year: int, current_year: int = 2026) -> str:
    """생년 → 연령대로 일반화.

    Args:
        birth_year: 출생 연도.
        current_year: 기준 연도 (기본 현재).

    Returns:
        연령대 문자열 (예: "50대").

    Examples:
        >>> generalize_age(1972)
        '50대'
    """
    age = current_year - birth_year
    decade = (age // 10) * 10
    return f"{decade}대"
```

#### Step 3. 결합 위험 평가

가명처리된 데이터를 외부 데이터와 결합했을 때 재식별 가능성이 있는지 평가:

- k-익명성 (k=5 이상 권장)
- l-다양성 (민감 속성 다양성)
- t-근접성 (분포 유사성)

```python
def k_anonymity_check(
    records: list[dict[str, Any]],
    quasi_identifiers: list[str],
    k: int = 5,
) -> bool:
    """k-익명성 검증.

    Args:
        records: 가명처리된 레코드 리스트.
        quasi_identifiers: 간접 식별자 컬럼명들.
        k: 최소 익명성 (기본 5).

    Returns:
        모든 그룹이 k 이상이면 True.
    """
    from collections import Counter

    keys = [
        tuple(r.get(qi) for qi in quasi_identifiers)
        for r in records
    ]
    counts = Counter(keys)
    return all(c >= k for c in counts.values())
```

### 민감정보 분류 (반드시 준수)

| 데이터 | 분류 | 처리 방법 |
|--------|------|---------|
| 이름·전화·이메일 | 직접 식별자 | 가명처리 시 제거 |
| 만성질환·복약 | **민감정보 (의료)** | AES-256 암호화 + 별도 동의 |
| 검진 결과 | **민감정보 (의료)** | AES-256 암호화 + 별도 동의 |
| 걸음수·심박수 | **민감정보 (생체)** | AES-256 암호화 + 별도 동의 |
| 키·몸무게·BMI | 일반 개인정보 | 일반 동의 |
| 영양제·식단 사진 | 일반 개인정보 | 30일 후 자동 폐기 |

---

## 📥 데이터 수집 표준 절차

### KDRIs 디지털화

```
1. 한국영양학회 자료실에서 KDRIs 2020 PDF 다운로드
2. 표 영역 OCR (Tabula 또는 수동 전사)
3. CSV 정형화 (kdris_metadata.json 스키마 준수)
4. 검수: 식약처 식품안전나라 일부 표본과 비교
5. data/kdris/kdris_2020.csv 커밋
6. 변경 사항을 docs/09-data-catalog.md §3.1 에 기록
```

#### CSV 컬럼 표준

```csv
code,name_ko,name_en,unit,sex,age_min,age_max,rda,ai,ear,ul,is_pregnant,is_lactating
vitamin_c_mg,비타민 C,Vitamin C,mg,male,19,29,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,19,29,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,,,110,,85,2000,true,false
calcium_mg,칼슘,Calcium,mg,male,19,29,800,,650,2500,false,false
...
```

### 식약처 API 연동

```
1. 공공데이터포털 회원가입 → API 키 발급
2. 키를 backend/.env 에 저장 (MFDS_API_KEY)
3. 첫 호출로 응답 형식 확인 (sample/mfds_response.json 저장)
4. SQLAlchemy 모델 정의 (src/models/db/food.py)
5. 동기화 스크립트 작성 (scripts/sync_mfds_data.py)
6. 분기마다 cron 또는 GitHub Actions로 자동 실행
```

### AI Hub 데이터셋 신청

```
1. AI Hub 회원가입 (NIA 운영)
2. 한국 음식 이미지 데이터셋 활용 신청서 작성
   - 사용 목적: AI 헬스케어 R&D, 학술 프로젝트
   - 지도교수 확인서 첨부 (요구 시)
3. 승인 대기 (3~5 영업일)
4. 다운로드 후 체크섬 검증
5. data/ 폴더에는 작은 샘플만 보관, 원본은 외부 스토리지
6. 사용 시 출처 명시 (앱 내 "정보 출처" 페이지)
```

> 📖 **상세**: [docs/09-data-catalog.md §4](../docs/09-data-catalog.md)

---

## 🔄 데이터 갱신 정책

| 데이터 | 갱신 빈도 | 트리거 |
|--------|---------|-------|
| KDRIs | 개정 발표 시 즉시 | 한국영양학회 알림 (수동) |
| 식약처 식품영양성분 API | 분기 자동 동기화 | GitHub Actions cron |
| 식약처 건강기능식품 원료 DB | 변경 알림 시 수동 | 식약처 보도자료 모니터링 |
| 농진청 식품성분표 | 새 개정판 발표 시 | 농진청 알림 (수동) |
| AI Hub 데이터셋 | 새 버전 공개 시 | AI Hub 알림 (수동) |

### 갱신 시 표준 절차

```
1. 새 데이터 다운로드 → data/raw/ (gitignore)
2. 정형화 → data/{source}/ (커밋 대상)
3. metadata.json 의 version, downloaded_at 갱신
4. 테스트 데이터로 회귀 테스트 (이전 버전과 차이 비교)
5. CHANGELOG.md (해당 폴더) 에 변경 사항 기록
6. PR 생성 → 영양·도메인 담당자 리뷰
```

---

## 🧪 데이터 검증 표준

### 데이터 무결성 체크 함수

```python
"""KDRIs 데이터 무결성 검증."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field


class KDRIsRow(BaseModel):
    """KDRIs CSV 한 행."""

    code: str = Field(..., pattern=r"^[a-z_]+_[a-z]+$")
    name_ko: str
    name_en: str
    unit: str = Field(..., pattern=r"^(mg|μg|ug|g|IU|kcal)$")
    sex: str = Field(..., pattern=r"^(male|female|all)$")
    age_min: int | None = Field(None, ge=0, le=120)
    age_max: int | None = Field(None, ge=0, le=120)
    rda: float | None = Field(None, ge=0)
    ai: float | None = Field(None, ge=0)
    ear: float | None = Field(None, ge=0)
    ul: float | None = Field(None, ge=0)
    is_pregnant: bool = False
    is_lactating: bool = False


def validate_kdris_csv(path: Path) -> list[str]:
    """KDRIs CSV의 무결성을 검증한다.

    Args:
        path: 검증할 CSV 경로.

    Returns:
        검증 오류 메시지 리스트. 비어있으면 통과.

    Examples:
        >>> errors = validate_kdris_csv(Path("data/kdris/kdris_2020.csv"))
        >>> assert not errors, errors
    """
    df = pd.read_csv(path)
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            KDRIsRow(**row.to_dict())
        except Exception as e:
            errors.append(f"Row {idx}: {e}")

    # RDA·AI·EAR·UL 중 최소 하나는 있어야 함
    no_value = df[df[["rda", "ai", "ear", "ul"]].isna().all(axis=1)]
    if not no_value.empty:
        errors.append(f"{len(no_value)} rows have no RDA/AI/EAR/UL")

    # 영양소별 19~29세 남녀 데이터 필수
    required = (
        df[(df["age_min"] == 19) & (df["age_max"] == 29)]
        ["code"].nunique()
    )
    total = df["code"].nunique()
    if required < total:
        errors.append(
            f"{total - required} nutrients missing 19-29 age range"
        )

    return errors
```

### 정기 검증 스크립트

`scripts/validate_data.py` 를 만들어 CI에서 자동 실행:

```bash
python scripts/validate_data.py
# Validates:
# - data/kdris/kdris_2020.csv
# - data/mfds/functional_ingredients.csv
# - data/reference/disease_codes.json
# Exit 0 if all pass, 1 if any error
```

GitHub Actions 워크플로 (`.github/workflows/ci-data.yml`):

```yaml
name: Data CI
on:
  push:
    paths: ["data/**"]
  pull_request:
    paths: ["data/**"]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pandas pydantic
      - run: python scripts/validate_data.py
```

---

## 🔐 보안 체크리스트 (데이터 작업 시)

- [ ] `.env` 파일에 API 키 저장 (절대 커밋 X)
- [ ] `.gitignore` 에 `data/raw/`, `data/private/` 추가 확인
- [ ] 사용자 데이터 (개인정보) 절대 `data/` 에 보관 X
- [ ] 영양제 라벨 샘플 사진은 **저작권 확인 후** `data/sample/` 에 (문제 시 일러스트 대체)
- [ ] 가명처리된 데이터라도 결합 위험 확인 (k≥5)
- [ ] 외부 데이터 사용 시 라이선스 호환성 확인
- [ ] 큰 파일은 Git LFS 또는 외부 저장 (저장소 비대화 방지)

---

## 📜 데이터 라이선스 매트릭스

| 출처 | 라이선스 | 의무 |
|------|---------|------|
| KDRIs (한국영양학회) | 공공저작물 자유이용 | 출처 표시 |
| 식약처 Open API | 공공데이터 (활용 동의) | 출처 표시 + API 키 |
| 농진청 식품성분 | 공공저작물 자유이용 | 출처 표시 |
| AI Hub 데이터셋 | 활용 동의 + 비상업 | **재배포 금지**, 사용 목적 준수 |
| 식약처 건강기능식품 원료 DB | 공공데이터 | 출처 표시 |

> ⚠️ **AI Hub 데이터셋은 재배포 금지**. data/ 폴더에는 출처·메타만, 실제 데이터는 외부에.

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../CLAUDE.md) — 프로젝트 루트 컨텍스트
- [`/data/README.md`](./README.md) — 사용자 노출용 출처·라이선스
- [`/docs/09-data-catalog.md`](../docs/09-data-catalog.md) — 12종 데이터·API 카탈로그
- [`/docs/10-compliance-checklist.md`](../docs/10-compliance-checklist.md) — 개인정보·가명정보 처리

---

**마지막 갱신**: 2026-05-03 | **버전**: v1.0
