# dev-guides/05 — KDRIs 룩업 + 영양 기준 조회

> **Phase**: 1 | **선행 작업**: [`01-bmi-and-v1-algorithm.md`](./01-bmi-and-v1-algorithm.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

KDRIs(한국인 영양소 섭취기준) 룩업 테이블을 메모리에 로드하고, 사용자 프로필(나이·성별·임신·수유부)에 맞는 권장 섭취량을 조회하는 모듈을 구현한다.

> 💡 **Phase 1 범위**: 메모리 룩업만. DB 마이그레이션·시드는 Phase 1 후반에 별도.

---

## 📋 산출물

```
backend/
├── src/
│   ├── models/schemas/
│   │   └── nutrition.py          # NutrientCode enum, KDRIsValue, NutrientStatus
│   └── nutrition/
│       ├── __init__.py
│       └── kdris.py              # KDRIs 룩업 모듈
├── tests/unit/nutrition/
│   ├── __init__.py
│   ├── test_kdris.py
│   └── fixtures/
│       └── kdris_sample.csv      # 테스트용 작은 KDRIs 샘플
data/
├── kdris/
│   ├── kdris_2020.csv            # 메인 (디지털화 후)
│   └── kdris_metadata.json       # 메타정보
└── reference/
    └── nutrient_codes.json       # 영양소 표준 코드
```

---

## 📐 데이터 명세

> 🔍 **출처**: [docs/09-data-catalog.md §3.1](../09-data-catalog.md), [data/CLAUDE.md](../../data/CLAUDE.md), [docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md)

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| KDRIs 2020 | A | 보건복지부·한국영양학회 자료를 기준 데이터로 사용한다. |
| RDA/AI/EAR/UL 해석 | A | National Academies DRI 정의를 참고해 필드 의미와 사용 범위를 명확히 한다. |
| 질환자 개인 처방 | 범위 밖 | KDRIs는 건강한 집단의 섭취 기준이므로 치료 용량 또는 개인 진단 기준으로 사용하지 않는다. |

> CSV에는 원자료 출처 URL, 버전, 디지털화 담당자, 검수 일자를 `kdris_metadata.json`에 함께 기록한다.

### KDRIs CSV 스키마

```csv
code,name_ko,name_en,unit,sex,age_min,age_max,rda,ai,ear,ul,is_pregnant,is_lactating
vitamin_c_mg,비타민 C,Vitamin C,mg,male,19,29,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,19,29,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,,,110,,85,2000,true,false
calcium_mg,칼슘,Calcium,mg,male,19,29,800,,650,2500,false,false
...
```

#### 컬럼 정의

| 컬럼 | 의미 | 필수 |
|------|------|------|
| `code` | 영양소 표준 코드 (e.g., `vitamin_c_mg`) | ✅ |
| `name_ko` | 한국어 영양소명 | ✅ |
| `name_en` | 영어 영양소명 | ✅ |
| `unit` | 단위 (mg, μg, g, IU, kcal) | ✅ |
| `sex` | 성별 (male/female/all) | ✅ |
| `age_min` | 연령 최소 (만 나이) | △ (임신부·수유부는 빈 값) |
| `age_max` | 연령 최대 | △ |
| `rda` | 권장 섭취량 | △ (rda/ai/ear 중 최소 1개) |
| `ai` | 충분 섭취량 | △ |
| `ear` | 평균 필요량 | △ |
| `ul` | 상한 섭취량 | △ |
| `is_pregnant` | 임신부 별도 행 여부 | ✅ (true/false) |
| `is_lactating` | 수유부 별도 행 여부 | ✅ (true/false) |

---

## 🔧 구현 명세

### 1. `src/models/schemas/nutrition.py`

```python
"""영양 분석 관련 스키마."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class NutrientStatus(StrEnum):
    """영양소 섭취 상태 분류.

    Reference:
        docs/07-core-algorithm.md §4.3
    """

    DEFICIENT = "deficient"      # 35% 미만 (심각한 결핍)
    LOW = "low"                  # 35~70% (부족)
    ADEQUATE = "adequate"        # 70~130% (적정)
    EXCESSIVE = "excessive"      # 130% 초과 (과다)
    RISKY = "risky"              # UL 초과 (위험)


class KDRIsValue(BaseModel):
    """단일 영양소의 KDRIs 권장값.

    Attributes:
        code: 영양소 표준 코드.
        name_ko: 한국어 영양소명.
        name_en: 영어 영양소명.
        unit: 단위.
        rda: 권장 섭취량 (있으면 우선).
        ai: 충분 섭취량 (RDA 없을 때 fallback).
        ear: 평균 필요량.
        ul: 상한 섭취량 (None이면 미설정).
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., pattern=r"^[a-z_]+_[a-z]+$")
    name_ko: str
    name_en: str
    unit: str
    rda: float | None = None
    ai: float | None = None
    ear: float | None = None
    ul: float | None = None

    @property
    def reference_value(self) -> float | None:
        """진단 기준값. RDA 우선, 없으면 AI.

        Returns:
            기준값 (둘 다 없으면 None).
        """
        return self.rda if self.rda is not None else self.ai


class UserKDRIsContext(BaseModel):
    """KDRIs 룩업을 위한 사용자 컨텍스트.

    Attributes:
        age: 만 나이.
        sex: "male" | "female".
        is_pregnant: 임신부 여부 (여성만 의미 있음).
        is_lactating: 수유부 여부 (여성만 의미 있음).
    """

    model_config = ConfigDict(frozen=True)

    age: int = Field(..., ge=1, le=120)
    sex: str = Field(..., pattern=r"^(male|female)$")
    is_pregnant: bool = False
    is_lactating: bool = False
```

### 2. `src/nutrition/kdris.py`

```python
"""KDRIs 룩업 모듈.

CSV에서 KDRIs 데이터를 로드하여 사용자별 권장 섭취량을 조회한다.

Reference:
    docs/09-data-catalog.md §3.1
    data/CLAUDE.md
"""

from __future__ import annotations

import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Final

from src.models.schemas.nutrition import KDRIsValue, UserKDRIsContext


logger = logging.getLogger(__name__)


DEFAULT_KDRIS_PATH: Final[Path] = Path("data/kdris/kdris_2020.csv")
"""기본 KDRIs CSV 경로 (프로젝트 루트 기준)."""


def _parse_optional_float(value: str) -> float | None:
    """빈 문자열은 None, 숫자는 float로 변환."""
    return float(value) if value else None


def _parse_optional_int(value: str) -> int | None:
    """빈 문자열은 None, 숫자는 int로 변환."""
    return int(value) if value else None


def load_kdris_csv(path: Path = DEFAULT_KDRIS_PATH) -> list[dict]:
    """KDRIs CSV를 로드하여 행 리스트로 반환한다.

    Args:
        path: CSV 파일 경로.

    Returns:
        각 행을 dict로 변환한 리스트.

    Raises:
        FileNotFoundError: 파일이 없는 경우.
        ValueError: CSV 형식이 잘못된 경우.

    Examples:
        >>> rows = load_kdris_csv(Path("data/kdris/kdris_2020.csv"))
        >>> rows[0]["code"]
        'vitamin_c_mg'
    """
    if not path.exists():
        raise FileNotFoundError(f"KDRIs CSV not found: {path}")

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        raise ValueError(f"KDRIs CSV is empty: {path}")

    logger.info("Loaded %d KDRIs rows from %s", len(rows), path)
    return rows


def lookup_kdris_for_user(
    nutrient_code: str,
    user: UserKDRIsContext,
    rows: list[dict] | None = None,
) -> KDRIsValue | None:
    """사용자 컨텍스트에 맞는 KDRIs 값을 조회한다.

    매칭 우선순위:
        1. 임신부/수유부 (해당하는 경우)
        2. 성별 + 연령 범위 매칭
        3. all 성별 + 연령 매칭 (성별 무관 영양소)

    Args:
        nutrient_code: 영양소 코드 (e.g., "vitamin_c_mg").
        user: 사용자 컨텍스트.
        rows: 미리 로드한 행 리스트 (None이면 기본 경로에서 로드).

    Returns:
        매칭된 KDRIsValue, 또는 매칭 실패 시 None.

    Raises:
        FileNotFoundError: rows=None일 때 기본 CSV가 없는 경우.

    Examples:
        >>> user = UserKDRIsContext(age=50, sex="female")
        >>> kdris = lookup_kdris_for_user("vitamin_c_mg", user)
        >>> kdris.rda
        100.0
    """
    if rows is None:
        rows = _load_default_kdris()

    # 1. 임신부 우선
    if user.is_pregnant and user.sex == "female":
        for row in rows:
            if (
                row["code"] == nutrient_code
                and row["sex"] == "female"
                and row["is_pregnant"].lower() == "true"
            ):
                return _row_to_kdris_value(row)

    # 2. 수유부
    if user.is_lactating and user.sex == "female":
        for row in rows:
            if (
                row["code"] == nutrient_code
                and row["sex"] == "female"
                and row["is_lactating"].lower() == "true"
            ):
                return _row_to_kdris_value(row)

    # 3. 일반 (성별 + 연령)
    for row in rows:
        if row["code"] != nutrient_code:
            continue
        if row["sex"] not in (user.sex, "all"):
            continue

        age_min = _parse_optional_int(row["age_min"])
        age_max = _parse_optional_int(row["age_max"])
        if age_min is None or age_max is None:
            continue
        if not (age_min <= user.age <= age_max):
            continue

        if (
            row["is_pregnant"].lower() == "true"
            or row["is_lactating"].lower() == "true"
        ):
            continue  # 임신·수유 분기는 위에서만

        return _row_to_kdris_value(row)

    logger.warning(
        "No KDRIs match for nutrient=%s, age=%d, sex=%s",
        nutrient_code, user.age, user.sex,
    )
    return None


def _row_to_kdris_value(row: dict) -> KDRIsValue:
    """CSV 행을 KDRIsValue로 변환."""
    return KDRIsValue(
        code=row["code"],
        name_ko=row["name_ko"],
        name_en=row["name_en"],
        unit=row["unit"],
        rda=_parse_optional_float(row["rda"]),
        ai=_parse_optional_float(row["ai"]),
        ear=_parse_optional_float(row["ear"]),
        ul=_parse_optional_float(row["ul"]),
    )


@lru_cache(maxsize=1)
def _load_default_kdris() -> list[dict]:
    """기본 경로에서 KDRIs를 1회만 로드 (캐시)."""
    return load_kdris_csv()
```

### 3. 테스트용 샘플 CSV

`tests/unit/nutrition/fixtures/kdris_sample.csv`:

```csv
code,name_ko,name_en,unit,sex,age_min,age_max,rda,ai,ear,ul,is_pregnant,is_lactating
vitamin_c_mg,비타민 C,Vitamin C,mg,male,19,29,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,19,29,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,male,30,49,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,30,49,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,male,50,64,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,50,64,100,,75,2000,false,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,,,110,,85,2000,true,false
vitamin_c_mg,비타민 C,Vitamin C,mg,female,,,140,,100,2000,false,true
calcium_mg,칼슘,Calcium,mg,male,19,29,800,,650,2500,false,false
calcium_mg,칼슘,Calcium,mg,female,19,29,700,,550,2500,false,false
calcium_mg,칼슘,Calcium,mg,male,50,64,750,,600,2500,false,false
calcium_mg,칼슘,Calcium,mg,female,50,64,800,,650,2500,false,false
iron_mg,철분,Iron,mg,male,19,29,10,,8,45,false,false
iron_mg,철분,Iron,mg,female,19,29,14,,11,45,false,false
iron_mg,철분,Iron,mg,female,,,24,,21,45,true,false
water_ml,수분,Water,ml,male,19,29,,2600,,,false,false
water_ml,수분,Water,ml,female,19,29,,2100,,,false,false
```

---

## 🧪 단위 테스트

### `tests/unit/nutrition/test_kdris.py`

```python
"""KDRIs 룩업 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.schemas.nutrition import KDRIsValue, UserKDRIsContext
from src.nutrition.kdris import (
    load_kdris_csv,
    lookup_kdris_for_user,
)


SAMPLE_CSV = Path("tests/unit/nutrition/fixtures/kdris_sample.csv")


@pytest.fixture
def sample_rows() -> list[dict]:
    """샘플 KDRIs CSV 로드."""
    return load_kdris_csv(SAMPLE_CSV)


class TestLoadKdrisCsv:
    """CSV 로딩 테스트."""

    def test_load_sample_returns_rows(self, sample_rows: list[dict]) -> None:
        assert len(sample_rows) > 0

    def test_load_nonexistent_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_kdris_csv(Path("/nonexistent.csv"))

    def test_first_row_has_code(self, sample_rows: list[dict]) -> None:
        assert sample_rows[0]["code"] == "vitamin_c_mg"


class TestLookupBasic:
    """기본 룩업 (성별 + 연령) 테스트."""

    def test_lookup_male_30_vitamin_c(self, sample_rows: list[dict]) -> None:
        """30세 남성 비타민C → 100mg RDA."""
        user = UserKDRIsContext(age=30, sex="male")
        result = lookup_kdris_for_user("vitamin_c_mg", user, rows=sample_rows)
        assert result is not None
        assert result.rda == 100.0
        assert result.unit == "mg"
        assert result.name_ko == "비타민 C"

    def test_lookup_female_50_calcium(self, sample_rows: list[dict]) -> None:
        """50세 여성 칼슘 → 800mg."""
        user = UserKDRIsContext(age=50, sex="female")
        result = lookup_kdris_for_user("calcium_mg", user, rows=sample_rows)
        assert result is not None
        assert result.rda == 800.0

    def test_lookup_female_50_iron(self, sample_rows: list[dict]) -> None:
        """폐경 후 여성 철분 (샘플엔 50세 데이터 없음 → None)."""
        user = UserKDRIsContext(age=50, sex="female")
        result = lookup_kdris_for_user("iron_mg", user, rows=sample_rows)
        # 50대 여성 철분은 샘플에 없으니 None 반환
        # 실제 KDRIs에서는 폐경 후 철분 권장량 ↓
        assert result is None


class TestLookupSpecial:
    """임신부·수유부 분기 테스트."""

    def test_lookup_pregnant_vitamin_c(self, sample_rows: list[dict]) -> None:
        """임신부 비타민C → 110mg (일반 100보다 높음)."""
        user = UserKDRIsContext(
            age=30, sex="female", is_pregnant=True
        )
        result = lookup_kdris_for_user("vitamin_c_mg", user, rows=sample_rows)
        assert result is not None
        assert result.rda == 110.0

    def test_lookup_lactating_vitamin_c(self, sample_rows: list[dict]) -> None:
        """수유부 비타민C → 140mg."""
        user = UserKDRIsContext(
            age=30, sex="female", is_lactating=True
        )
        result = lookup_kdris_for_user("vitamin_c_mg", user, rows=sample_rows)
        assert result is not None
        assert result.rda == 140.0

    def test_lookup_pregnant_priority_over_age(
        self, sample_rows: list[dict]
    ) -> None:
        """임신부 분기는 일반 연령 분기보다 우선."""
        user = UserKDRIsContext(
            age=30, sex="female", is_pregnant=True
        )
        result = lookup_kdris_for_user("iron_mg", user, rows=sample_rows)
        assert result is not None
        assert result.rda == 24.0  # 임신부 철분 (일반 14보다 ↑)

    def test_lookup_male_pregnancy_flag_ignored(
        self, sample_rows: list[dict]
    ) -> None:
        """남성에 is_pregnant=True 줘도 일반 분기로 폴백."""
        user = UserKDRIsContext(
            age=30, sex="male", is_pregnant=True
        )
        result = lookup_kdris_for_user("vitamin_c_mg", user, rows=sample_rows)
        assert result is not None
        assert result.rda == 100.0  # 일반 남성 값


class TestLookupAI:
    """AI(충분섭취량) 폴백 테스트."""

    def test_lookup_water_uses_ai(self, sample_rows: list[dict]) -> None:
        """수분은 RDA 없고 AI만 → reference_value는 AI."""
        user = UserKDRIsContext(age=25, sex="male")
        result = lookup_kdris_for_user("water_ml", user, rows=sample_rows)
        assert result is not None
        assert result.rda is None
        assert result.ai == 2600.0
        assert result.reference_value == 2600.0


class TestLookupNotFound:
    """매칭 실패 케이스."""

    def test_unknown_nutrient(self, sample_rows: list[dict]) -> None:
        """존재하지 않는 영양소."""
        user = UserKDRIsContext(age=30, sex="male")
        result = lookup_kdris_for_user("unobtainium_mg", user, rows=sample_rows)
        assert result is None

    def test_age_out_of_range(self, sample_rows: list[dict]) -> None:
        """연령 범위 밖 (샘플 CSV는 19~64만)."""
        user = UserKDRIsContext(age=80, sex="male")
        result = lookup_kdris_for_user("vitamin_c_mg", user, rows=sample_rows)
        assert result is None


class TestKDRIsValue:
    """KDRIsValue 모델 테스트."""

    def test_reference_value_uses_rda(self) -> None:
        v = KDRIsValue(
            code="test_mg", name_ko="테스트", name_en="Test", unit="mg",
            rda=100.0, ai=80.0,
        )
        assert v.reference_value == 100.0

    def test_reference_value_falls_back_to_ai(self) -> None:
        v = KDRIsValue(
            code="test_mg", name_ko="테스트", name_en="Test", unit="mg",
            rda=None, ai=80.0,
        )
        assert v.reference_value == 80.0

    def test_reference_value_none_when_neither(self) -> None:
        v = KDRIsValue(
            code="test_mg", name_ko="테스트", name_en="Test", unit="mg",
            rda=None, ai=None,
        )
        assert v.reference_value is None

    def test_invalid_code_pattern_raises(self) -> None:
        with pytest.raises(ValueError):
            KDRIsValue(
                code="InvalidCode",  # 대문자 X
                name_ko="x", name_en="x", unit="mg",
            )

    def test_frozen_immutable(self) -> None:
        v = KDRIsValue(
            code="test_mg", name_ko="테스트", name_en="Test", unit="mg",
            rda=100.0,
        )
        with pytest.raises(Exception):  # frozen=True
            v.rda = 200.0  # type: ignore[misc]
```

---

## ✅ Definition of Done

- [ ] `src/models/schemas/nutrition.py` — NutrientStatus enum, KDRIsValue, UserKDRIsContext
- [ ] `src/nutrition/kdris.py` — load_kdris_csv, lookup_kdris_for_user, _row_to_kdris_value, _load_default_kdris
- [ ] `tests/unit/nutrition/fixtures/kdris_sample.csv` — 17행 샘플
- [ ] `tests/unit/nutrition/test_kdris.py` — 15+ 테스트
- [ ] 임신부 분기 테스트 (vitamin C 110mg, iron 24mg)
- [ ] 수유부 분기 테스트 (vitamin C 140mg)
- [ ] AI 폴백 테스트 (water 2,600 ml)
- [ ] 매칭 실패 케이스 (unknown nutrient, age out of range)
- [ ] `KDRIsValue.reference_value` 프로퍼티 테스트 (RDA 우선, AI 폴백)
- [ ] `frozen=True` 불변성 테스트
- [ ] 모든 함수 Google-style docstring + Examples
- [ ] 모든 함수 타입 힌트
- [ ] `mypy src/nutrition src/models/schemas/nutrition.py --strict` 통과
- [ ] `pytest tests/unit/nutrition -v` 통과
- [ ] 코드 커버리지 ≥ 90%

---

## 💡 구현 팁

### CSV 빈 셀 처리

```python
# CSV에서 RDA가 없는 영양소는 빈 셀
# pandas.read_csv 는 NaN, 표준 csv 는 ""

# DictReader는 빈 셀을 "" 로 반환
def _parse_optional_float(value: str) -> float | None:
    return float(value) if value else None
```

### 매칭 우선순위 (분기 순서가 중요)

```python
# 1) 임신부/수유부 우선
# 2) 성별 + 연령 매칭
# 3) all (성별 무관) 매칭

# 잘못 작성하면: 일반 연령 매칭이 먼저 발동 → 임신부 데이터 누락
```

### lru_cache 주의

```python
@lru_cache(maxsize=1)
def _load_default_kdris() -> list[dict]:
    """기본 경로에서 1회만 로드."""
    return load_kdris_csv()
```

→ 운영 시 CSV가 갱신되면 프로세스 재시작 필요. 단위 테스트에서는 `rows` 인자로 우회 가능.

### 향후 DB 마이그레이션 시

이 구현은 **메모리 룩업** 기반. 향후 PostgreSQL로 마이그레이션 시:

```python
# 인터페이스만 동일하게, 구현만 교체
class KDRIsRepository(Protocol):
    async def lookup(self, code: str, user: UserKDRIsContext) -> KDRIsValue | None: ...

class CsvKDRIsRepository(KDRIsRepository):
    def __init__(self, path: Path): ...
    async def lookup(...) -> KDRIsValue | None: ...

class PostgresKDRIsRepository(KDRIsRepository):
    def __init__(self, session: AsyncSession): ...
    async def lookup(...) -> KDRIsValue | None: ...
```

→ Adapter 패턴으로 추후 교체 비용 ↓.

### 실제 KDRIs 2020 디지털화는 별도 작업

이 작업에서는 **샘플 CSV** (17행) 만 만들고 모듈 동작을 검증. 실제 30종 영양소 × 연령·성별 × 임신·수유 풀 데이터는 **Phase 0 산출물 (DD 역할)** 에서 디지털화.

---

## 🚫 이 작업에서 하지 말 것

- ❌ DB 마이그레이션 (Alembic) 작성 — Phase 1 후반
- ❌ FastAPI 라우터 — Phase 1 후반
- ❌ 부족 영양소 진단 로직 — Phase 2 (`dev-guides/06`, 추후 작성)
- ❌ 실제 KDRIs 2020 PDF → CSV 디지털화 — DD 역할 (Phase 0)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/data/CLAUDE.md`](../../data/CLAUDE.md)
- [`/docs/09-data-catalog.md §3.1`](../09-data-catalog.md)
- 이전 작업: [`04-weight-prediction-7step.md`](./04-weight-prediction-7step.md)
- 다음 단계 (Phase 2): 부족 영양소 진단 (별도 작성 예정)
