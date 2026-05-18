"""정적 데이터(KDRIs / 영양소 코드 / MFDS) 무결성 검증.

CI 의 ``ci-backend-yeong.yml`` 에서 실행된다. 0 오류면 ``exit 0``,
1건 이상이면 ``exit 1``.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-03-nutrition-data.md Step 11
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field, ValidationError

DATA_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent / "data"

KDRIS_CSV: Final[Path] = DATA_ROOT / "kdris" / "kdris_2020.csv"
NUTRIENT_CODES: Final[Path] = DATA_ROOT / "reference" / "nutrient_codes.json"
DISEASE_CODES: Final[Path] = DATA_ROOT / "reference" / "disease_codes.json"
MFDS_CSV: Final[Path] = DATA_ROOT / "mfds" / "functional_ingredients.csv"


class KDRIsRow(BaseModel):
    """KDRIs CSV row 검증 스키마."""

    code: str = Field(..., pattern=r"^[a-z][a-z0-9_]+$")
    name_ko: str = Field(..., min_length=1)
    name_en: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    sex: str = Field(..., pattern=r"^(male|female|all)$")
    age_min: int = Field(..., ge=0, le=200)
    age_max: int = Field(..., ge=0, le=200)
    rda: float | None = None
    ai: float | None = None
    ear: float | None = None
    ul: float | None = None
    is_pregnant: bool = False
    is_lactating: bool = False


def _parse_optional_float(value: str) -> float | None:
    return float(value) if value else None


def _parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def validate_kdris_csv(path: Path) -> list[str]:
    if not path.is_file():
        return [f"Missing file: {path}"]
    errors: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for i, raw in enumerate(csv.DictReader(f), start=2):
            try:
                KDRIsRow(
                    code=raw["code"],
                    name_ko=raw["name_ko"],
                    name_en=raw["name_en"],
                    unit=raw["unit"],
                    sex=raw["sex"],
                    age_min=int(raw["age_min"]),
                    age_max=int(raw["age_max"]),
                    rda=_parse_optional_float(raw["rda"]),
                    ai=_parse_optional_float(raw["ai"]),
                    ear=_parse_optional_float(raw["ear"]),
                    ul=_parse_optional_float(raw["ul"]),
                    is_pregnant=_parse_bool(raw["is_pregnant"]),
                    is_lactating=_parse_bool(raw["is_lactating"]),
                )
            except (ValidationError, KeyError, ValueError) as exc:
                errors.append(f"KDRIs row {i}: {exc}")
                continue

            if not any(raw[k] for k in ("rda", "ai", "ear", "ul")):
                errors.append(f"KDRIs row {i}: no RDA/AI/EAR/UL value")
    return errors


def validate_nutrient_codes(path: Path) -> list[str]:
    if not path.is_file():
        return [f"Missing file: {path}"]
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for code, info in data.items():
        if code.startswith("_"):
            continue
        for key in ("name_ko", "name_en", "unit"):
            if key not in info:
                errors.append(f"nutrient_codes: {code} missing {key}")
    return errors


def validate_disease_codes(path: Path) -> list[str]:
    if not path.is_file():
        return [f"Missing file: {path}"]
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for code, info in data.items():
        if code.startswith("_"):
            continue
        for key in ("name_ko", "name_en", "icd10", "weight_v4"):
            if key not in info:
                errors.append(f"disease_codes: {code} missing {key}")
    return errors


def validate_mfds_csv(path: Path) -> list[str]:
    if not path.is_file():
        return [f"Missing file: {path}"]
    errors: list[str] = []
    nutrient_codes_data = json.loads(NUTRIENT_CODES.read_text(encoding="utf-8"))
    valid_codes = {c for c in nutrient_codes_data if not c.startswith("_")}
    with path.open("r", encoding="utf-8", newline="") as f:
        for i, raw in enumerate(csv.DictReader(f), start=2):
            code = raw["nutrient_code"].strip()
            if code not in valid_codes:
                errors.append(f"MFDS row {i}: nutrient_code {code!r} not in nutrient_codes.json")
            if not raw["ingredient_name_ko"].strip():
                errors.append(f"MFDS row {i}: empty ingredient_name_ko")
    return errors


def main() -> int:
    all_errors: list[str] = []
    all_errors.extend(validate_kdris_csv(KDRIS_CSV))
    all_errors.extend(validate_nutrient_codes(NUTRIENT_CODES))
    all_errors.extend(validate_disease_codes(DISEASE_CODES))
    all_errors.extend(validate_mfds_csv(MFDS_CSV))

    if all_errors:
        for err in all_errors:
            print(f"[ERROR] {err}", file=sys.stderr)
        return 1
    print("[OK] All data files passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
