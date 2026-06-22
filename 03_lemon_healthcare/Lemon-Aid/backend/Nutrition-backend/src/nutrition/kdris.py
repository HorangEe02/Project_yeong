"""KDRIs 기준값 룩업."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import TypedDict, cast

from src.config import (
    PROJECT_ROOT,
    Settings,
    get_settings,
    resolve_nutrition_reference_root,
)
from src.models.schemas.nutrition import KDRIReference
from src.models.schemas.user import PregnancyStatus, Sex

NUTRITION_REFERENCE_ROOT = resolve_nutrition_reference_root()
KDRIS_REFERENCE_ROOT = NUTRITION_REFERENCE_ROOT / "kdris"
DEFAULT_KDRIS_2020_CSV = KDRIS_REFERENCE_ROOT / "kdris_2020.csv"
DEFAULT_KDRIS_2025_CSV = KDRIS_REFERENCE_ROOT / "kdris_2025.csv"
DEFAULT_KDRIS_CSV = DEFAULT_KDRIS_2020_CSV
DEFAULT_KDRIS_METADATA = KDRIS_REFERENCE_ROOT / "kdris_metadata.json"
DEFAULT_KDRIS_SOURCE_MANIFEST = KDRIS_REFERENCE_ROOT / "kdris_source_manifest.json"
DATASET_STATUS_FALLBACK = "sample_fixture"
DATASET_VERSION_FALLBACK = "2020-sample"
SOURCE_MANIFEST_VERSION_FALLBACK = "unknown"
SEX_ALL = "all"
REFERENCE_TYPE_PRIORITY = {
    "RNI": 0,
    "RDA": 0,
    "AI": 1,
    "EER": 2,
    "EAR": 3,
    "CDRR": 4,
    "AMDR": 5,
    "policy_limit": 6,
    "UL": 6,
}


class KDRIMetadata(TypedDict, total=False):
    """KDRIs 메타데이터 파일 구조."""

    status: str
    dataset: str
    not_production: bool


class KDRIDatasetContext(TypedDict):
    """현재 런타임 KDRIs 데이터셋 문맥."""

    dataset_status: str
    dataset_version: str
    source_manifest_version: str


def _parse_optional_float(value: str | None) -> float | None:
    """빈 문자열을 허용하는 float parser.

    Args:
        value: CSV 셀 값.

    Returns:
        float 값 또는 None.
    """
    if value is None or value == "":
        return None
    return float(value)


def _parse_optional_text(value: str | None) -> str | None:
    """빈 문자열을 허용하는 문자열 parser.

    Args:
        value: CSV 셀 값.

    Returns:
        문자열 또는 None.
    """
    if value is None or value == "":
        return None
    return value


def _resolve_project_path(path_value: str | None) -> Path | None:
    """설정 문자열을 프로젝트 기준 경로로 변환한다.

    Args:
        path_value: 절대 경로 또는 프로젝트 루트 기준 상대 경로.

    Returns:
        Path 객체 또는 None.
    """
    if path_value is None or path_value == "":
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def resolve_kdris_data_path(
    kdris_data_version: str,
    kdris_data_path: str | None = None,
) -> Path:
    """KDRIs 설정값을 실제 CSV 경로로 해석한다.

    Args:
        kdris_data_version: 설정된 KDRIs 데이터셋 버전.
        kdris_data_path: 명시적 CSV 경로.

    Returns:
        KDRIs CSV 경로.
    """
    explicit_path = _resolve_project_path(kdris_data_path)
    if explicit_path is not None:
        return explicit_path
    if kdris_data_version == "2025":
        return DEFAULT_KDRIS_2025_CSV
    return DEFAULT_KDRIS_2020_CSV


def get_configured_kdris_path(settings: Settings | None = None) -> Path:
    """현재 설정에 따른 KDRIs CSV 경로를 반환한다.

    Args:
        settings: 테스트 또는 수동 호출용 Settings 객체.

    Returns:
        KDRIs CSV 경로.
    """
    if settings is None:
        settings = get_settings()
    return resolve_kdris_data_path(
        kdris_data_version=settings.kdris_data_version,
        kdris_data_path=settings.kdris_data_path,
    )


def _legacy_age_to_months(age_years: int, is_upper_bound: bool = False) -> int:
    """기존 연 단위 나이를 월 단위 범위로 변환한다.

    Args:
        age_years: 만 나이 연 단위 값.
        is_upper_bound: 상한이면 해당 연령의 마지막 개월까지 포함한다.

    Returns:
        월 단위 나이.
    """
    if is_upper_bound:
        return (age_years * 12) + 11
    return age_years * 12


def _month_age_to_display_year(age_months: int) -> int:
    """월 단위 나이를 API 호환용 연 단위 값으로 변환한다.

    Args:
        age_months: 월 단위 나이.

    Returns:
        정수 연령.
    """
    return age_months // 12


def _parse_legacy_row(row: dict[str, str]) -> KDRIReference:
    """2020 샘플 fixture 행을 KDRIReference로 변환한다.

    Args:
        row: CSV row.

    Returns:
        KDRIReference 모델.
    """
    age_min = int(str(row["age_min"]))
    age_max = int(str(row["age_max"]))
    source_note = str(row["source_note"])
    return KDRIReference(
        nutrient_code=str(row["nutrient_code"]),
        nutrient_name=str(row["nutrient_name"]),
        nutrient_name_en=str(row["nutrient_name"]),
        sex=str(row["sex"]),
        age_min=age_min,
        age_max=age_max,
        age_min_months=_legacy_age_to_months(age_min),
        age_max_months=_legacy_age_to_months(age_max, is_upper_bound=True),
        pregnancy_status=cast(PregnancyStatus, str(row["pregnancy_status"])),
        reference_type=str(row["reference_type"]),
        reference_amount=float(str(row["reference_amount"])),
        reference_unit=str(row["reference_unit"]),
        ul_amount=_parse_optional_float(row.get("ul_amount")),
        ul_unit=row.get("ul_unit") or None,
        source_note=source_note,
        source_id="local_kdris_2020_sample_fixture",
        review_status="not_applicable_sample_fixture",
        dataset_version="2020-sample",
        source_manifest_version=get_source_manifest_version(),
    )


def _parse_2025_row(row: dict[str, str]) -> KDRIReference:
    """2025 운영 후보 스키마 행을 KDRIReference로 변환한다.

    Args:
        row: CSV row.

    Returns:
        KDRIReference 모델.
    """
    age_min_months = int(row["age_min_months"])
    age_max_months = int(row["age_max_months"])
    source_id = row["source_id"]
    source_table = row["source_table"]
    source_cell = row["source_cell"]
    nutrient_name_ko = row["nutrient_name_ko"]
    nutrient_name_en = row["nutrient_name_en"]
    return KDRIReference(
        nutrient_code=row["nutrient_code"],
        nutrient_name=nutrient_name_en or nutrient_name_ko,
        nutrient_name_ko=nutrient_name_ko,
        nutrient_name_en=nutrient_name_en,
        nutrient_group=row["nutrient_group"],
        sex=row["sex"],
        age_min=_month_age_to_display_year(age_min_months),
        age_max=_month_age_to_display_year(age_max_months),
        age_min_months=age_min_months,
        age_max_months=age_max_months,
        pregnancy_status=cast(PregnancyStatus, row["pregnancy_status"]),
        condition_detail=_parse_optional_text(row.get("condition_detail")),
        source_variant=_parse_optional_text(row.get("source_variant")),
        reference_type=row["reference_type"],
        reference_amount=_parse_optional_float(row.get("reference_amount")),
        reference_amount_min=_parse_optional_float(row.get("reference_amount_min")),
        reference_amount_max=_parse_optional_float(row.get("reference_amount_max")),
        reference_unit=row["reference_unit"],
        ul_amount=_parse_optional_float(row.get("ul_amount")),
        ul_unit=_parse_optional_text(row.get("ul_unit")),
        ul_amount_secondary=_parse_optional_float(row.get("ul_amount_secondary")),
        ul_unit_secondary=_parse_optional_text(row.get("ul_unit_secondary")),
        source_note=f"{source_id}:{source_table}:{source_cell}",
        source_id=source_id,
        source_artifact=row["source_artifact"],
        source_page=row["source_page"],
        source_table=source_table,
        source_cell=source_cell,
        errata_version=row["errata_version"],
        review_status=row["review_status"],
        reviewer_1=_parse_optional_text(row.get("reviewer_1")),
        reviewer_2=_parse_optional_text(row.get("reviewer_2")),
        reviewed_at=_parse_optional_text(row.get("reviewed_at")),
        dataset_version="2025",
        source_manifest_version=get_source_manifest_version(),
    )


def _parse_kdris_row(row: dict[str, str]) -> KDRIReference:
    """CSV 스키마에 맞는 row parser를 선택한다.

    Args:
        row: CSV row.

    Returns:
        KDRIReference 모델.
    """
    if "age_min_months" in row:
        return _parse_2025_row(row)
    return _parse_legacy_row(row)


@lru_cache
def _load_kdris_references_from_path(csv_path: Path) -> tuple[KDRIReference, ...]:
    """KDRIs CSV를 로드한다.

    Args:
        csv_path: KDRIs CSV 경로.

    Returns:
        KDRIReference tuple.
    """
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        rows = csv.DictReader(csv_file)
        return tuple(_parse_kdris_row(row) for row in rows)


def load_kdris_references(csv_path: Path | None = None) -> tuple[KDRIReference, ...]:
    """설정 또는 명시 경로의 KDRIs CSV를 로드한다.

    Args:
        csv_path: KDRIs CSV 경로. None이면 Settings 기반 경로를 사용한다.

    Returns:
        KDRIReference tuple.
    """
    resolved_path = get_configured_kdris_path() if csv_path is None else csv_path
    return _load_kdris_references_from_path(resolved_path)


@lru_cache
def load_kdris_metadata(metadata_path: Path = DEFAULT_KDRIS_METADATA) -> KDRIMetadata:
    """KDRIs 샘플 메타데이터를 로드한다.

    Args:
        metadata_path: 메타데이터 JSON 경로.

    Returns:
        메타데이터 dictionary.
    """
    with metadata_path.open(encoding="utf-8") as metadata_file:
        loaded: object = json.load(metadata_file)
    if not isinstance(loaded, dict):
        return {"status": DATASET_STATUS_FALLBACK}
    metadata = cast(dict[str, object], loaded)
    return {
        "status": str(metadata.get("status", DATASET_STATUS_FALLBACK)),
        "dataset": str(metadata.get("dataset", "")),
        "not_production": bool(metadata.get("not_production", True)),
    }


def get_dataset_status() -> str:
    """현재 KDRIs 데이터셋 상태 문자열을 반환한다.

    Returns:
        메타데이터에 기록된 데이터셋 상태.
    """
    return get_kdris_dataset_context()["dataset_status"]


def get_dataset_version() -> str:
    """현재 KDRIs 데이터셋 버전을 반환한다.

    Returns:
        KDRIs 데이터셋 버전.
    """
    return get_kdris_dataset_context()["dataset_version"]


def get_source_manifest_version() -> str:
    """현재 KDRIs source manifest schema version을 반환한다.

    Returns:
        Source manifest schema version.
    """
    return get_kdris_dataset_context()["source_manifest_version"]


def get_kdris_dataset_context(settings: Settings | None = None) -> KDRIDatasetContext:
    """현재 런타임 KDRIs 데이터셋 추적 정보를 반환한다.

    Args:
        settings: 테스트 또는 수동 호출용 Settings 객체.

    Returns:
        데이터셋 상태, 버전, manifest version.
    """
    if settings is None:
        settings = get_settings()

    csv_path = resolve_kdris_data_path(
        kdris_data_version=settings.kdris_data_version,
        kdris_data_path=settings.kdris_data_path,
    )
    dataset_status = DATASET_STATUS_FALLBACK
    source_manifest_version = SOURCE_MANIFEST_VERSION_FALLBACK

    try:
        manifest_path = _resolve_project_path(settings.kdris_manifest_path)
        manifest = _load_manifest_context(manifest_path or DEFAULT_KDRIS_SOURCE_MANIFEST)
        source_manifest_version = str(
            manifest.get("schema_version", SOURCE_MANIFEST_VERSION_FALLBACK)
        )
        dataset_status = str(manifest.get("local_dataset_status", DATASET_STATUS_FALLBACK))
        artifact_status = _dataset_status_from_manifest(csv_path, manifest)
        if artifact_status is not None:
            dataset_status = artifact_status
    except (FileNotFoundError, ValueError):
        if settings.kdris_data_version == DATASET_VERSION_FALLBACK:
            metadata = load_kdris_metadata()
            dataset_status = metadata.get("status", DATASET_STATUS_FALLBACK)

    return {
        "dataset_status": dataset_status,
        "dataset_version": settings.kdris_data_version,
        "source_manifest_version": source_manifest_version,
    }


def _load_manifest_context(manifest_path: Path) -> Mapping[str, object]:
    """KDRIs source manifest를 dataset context용으로 로드한다.

    Args:
        manifest_path: Source manifest JSON path.

    Returns:
        Manifest mapping.

    Raises:
        ValueError: Manifest가 JSON object가 아닌 경우.
    """
    with manifest_path.open(encoding="utf-8") as manifest_file:
        loaded: object = json.load(manifest_file)
    if not isinstance(loaded, dict):
        raise ValueError("KDRIs source manifest must be a JSON object.")
    return cast(Mapping[str, object], loaded)


def _dataset_status_from_manifest(
    csv_path: Path,
    manifest: Mapping[str, object],
) -> str | None:
    """Manifest dataset_artifacts에서 CSV 상태를 찾는다.

    Args:
        csv_path: KDRIs CSV 경로.
        manifest: Source manifest.

    Returns:
        데이터셋 상태 또는 None.
    """
    artifacts = manifest.get("dataset_artifacts")
    if not isinstance(artifacts, list):
        return None
    try:
        relative_path = csv_path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        relative_path = csv_path.as_posix()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("path") == relative_path and isinstance(artifact.get("status"), str):
            return cast(str, artifact["status"])
    return None


def get_kdris_for_profile(
    age: int,
    sex: Sex,
    pregnancy_status: PregnancyStatus = "none",
) -> list[KDRIReference]:
    """프로필에 맞는 KDRIs 기준값 목록을 반환한다.

    Args:
        age: 만 나이.
        sex: "male" 또는 "female".
        pregnancy_status: 임신/수유 상태.

    Returns:
        매칭된 KDRIs 기준값 목록.
    """
    references = load_kdris_references()
    age_months = _legacy_age_to_months(age)
    baseline_matches = [
        reference
        for reference in references
        if (reference.age_min_months or _legacy_age_to_months(reference.age_min))
        <= age_months
        <= (reference.age_max_months or _legacy_age_to_months(reference.age_max, True))
        and reference.sex in (SEX_ALL, sex)
        and reference.pregnancy_status == "none"
    ]
    if pregnancy_status == "none":
        return baseline_matches

    condition_matches = [
        reference
        for reference in references
        if (reference.age_min_months or _legacy_age_to_months(reference.age_min))
        <= age_months
        <= (reference.age_max_months or _legacy_age_to_months(reference.age_max, True))
        and reference.sex in (SEX_ALL, sex)
        and reference.pregnancy_status == pregnancy_status
    ]
    if not condition_matches:
        return baseline_matches

    replacement_matches = [
        reference
        for reference in condition_matches
        if reference.condition_detail is None and reference.source_variant is None
    ]
    replacement_by_code = {reference.nutrient_code: reference for reference in replacement_matches}
    merged: list[KDRIReference] = []
    for reference in baseline_matches:
        merged.append(replacement_by_code.get(reference.nutrient_code, reference))
    seen_keys = {
        (
            reference.nutrient_code,
            reference.reference_type,
            reference.condition_detail,
            reference.source_variant,
        )
        for reference in merged
    }
    for reference in condition_matches:
        key = (
            reference.nutrient_code,
            reference.reference_type,
            reference.condition_detail,
            reference.source_variant,
        )
        if key not in seen_keys:
            merged.append(reference)
            seen_keys.add(key)
    return merged


def lookup_kdris_reference(
    nutrient_code: str,
    age: int,
    sex: Sex,
    pregnancy_status: PregnancyStatus = "none",
) -> KDRIReference | None:
    """영양소 코드 기준으로 KDRIs 기준값을 조회한다.

    Args:
        nutrient_code: 내부 영양소 코드.
        age: 만 나이.
        sex: "male" 또는 "female".
        pregnancy_status: 임신/수유 상태.

    Returns:
        매칭된 기준값. 없으면 None.
    """
    matches = [
        reference
        for reference in get_kdris_for_profile(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
        )
        if reference.nutrient_code == nutrient_code
    ]
    if not matches:
        return None
    return min(
        matches,
        key=lambda reference: REFERENCE_TYPE_PRIORITY.get(reference.reference_type, 99),
    )
