"""CSV-backed ERP adapter — Sprint 1 P0 PoC.

ERP 측이 nightly 로 추출한 CSV 파일을 읽어 `EmployeeRecord` 로 반환.
Sprint 3 에서 DB read-replica 또는 REST 어댑터로 승격 검토.

Environment:
    AJIN_ERP_CSV_PATH  — 필수. CSV 경로. 없으면 ValueError.
    AJIN_ERP_FIELD_MAPPING — 선택. YAML 매핑 경로 (default: config/erp_field_mapping.yaml).

CSV 컬럼: 매핑 YAML 에 정의. 기본 매핑은 [canonical_id, name, email, phone,
department, division, position, position_level, plant, hire_date, is_active].

권한 정책: MockErpAdapter 와 동일 (W7 4-tier). 실제 ERP 가 별도 권한
필드를 발행하면 Sprint 2 에서 overlay.

`fetch_extras` 는 mock 데이터를 반환하지 않는다 — CSV 에 trip/approval 정보는
없으므로 PARTIAL/DENIED 권한 분기만 수행하고 빈 trips/direct_reports/approvals
를 돌려준다. Sprint 2 의 LdapDirectoryAdapter / RestErpAdapter 가 보강할 영역.
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Iterator, Optional

from features.search.adapters.erp_adapter import (
    ApprovalSummary,
    DirectReport,
    EmployeeExtras,
    EmployeeRecord,
    ErpAdapter,
    TripRecord,
)

logger = logging.getLogger(__name__)


# ─── 기본 컬럼 매핑 (YAML 미지정 시 사용) ──────────────────────
DEFAULT_FIELD_MAPPING = {
    "canonical_id": "canonical_id",
    "name": "name",
    "email": "email",
    "phone": "phone",
    "department": "department",
    "division": "division",
    "position": "position",
    "position_level": "position_level",
    "plant": "plant",
    "hire_date": "hire_date",
    "is_active": "is_active",
}


def _load_field_mapping(path: Optional[Path]) -> dict[str, str]:
    if path is None or not path.exists():
        return DEFAULT_FIELD_MAPPING
    try:
        import yaml  # type: ignore
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return {k: str(v) for k, v in raw.items() if v}
    except ImportError:
        logger.warning("PyYAML not installed — using default field mapping")
        return DEFAULT_FIELD_MAPPING
    except Exception as e:
        logger.warning("field mapping load failed (%s) — using default", e)
        return DEFAULT_FIELD_MAPPING


def _coerce_int(v: object) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(str(v).strip())
    except ValueError:
        return None


def _coerce_bool(v: object, default: bool = True) -> bool:
    if v is None or v == "":
        return default
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "활성", "active"}:
        return True
    if s in {"0", "false", "no", "n", "퇴직", "비활성", "inactive"}:
        return False
    return default


class CsvErpAdapter(ErpAdapter):
    """CSV-backed ERP adapter."""

    def __init__(
        self,
        csv_path: Optional[Path] = None,
        field_mapping_path: Optional[Path] = None,
    ) -> None:
        env_csv = os.getenv("AJIN_ERP_CSV_PATH")
        if csv_path is None and not env_csv:
            raise ValueError(
                "CsvErpAdapter requires AJIN_ERP_CSV_PATH env or csv_path arg"
            )
        self.csv_path = Path(csv_path or env_csv)  # type: ignore[arg-type]
        if not self.csv_path.exists():
            raise FileNotFoundError(f"ERP CSV not found: {self.csv_path}")

        mapping_path = field_mapping_path or Path(
            os.getenv("AJIN_ERP_FIELD_MAPPING")
            or Path(__file__).resolve().parent.parent.parent.parent
            / "config"
            / "erp_field_mapping.yaml"
        )
        self.field_mapping = _load_field_mapping(mapping_path)

    # ─── iteration / lookup ────────────────────────────────

    def _row_to_record(self, row: dict[str, str]) -> Optional[EmployeeRecord]:
        m = self.field_mapping
        canonical_id = row.get(m["canonical_id"], "").strip()
        if not canonical_id:
            return None
        return EmployeeRecord(
            canonical_employee_id=canonical_id,
            name=row.get(m["name"], "").strip(),
            email=row.get(m.get("email", "email"), "").strip() or None,
            phone=row.get(m.get("phone", "phone"), "").strip() or None,
            department=row.get(m.get("department", "department"), "").strip() or None,
            division=row.get(m.get("division", "division"), "").strip() or None,
            position=row.get(m.get("position", "position"), "").strip() or None,
            position_level=_coerce_int(row.get(m.get("position_level", "position_level"))),
            plant=row.get(m.get("plant", "plant"), "").strip() or None,
            hire_date=row.get(m.get("hire_date", "hire_date"), "").strip() or None,
            is_active=_coerce_bool(row.get(m.get("is_active", "is_active"))),
        )

    def iter_employees(self) -> Iterator[EmployeeRecord]:
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = self._row_to_record(row)
                if rec is not None:
                    yield rec

    def fetch_employee_by_canonical_id(
        self, canonical_id: str
    ) -> Optional[EmployeeRecord]:
        for rec in self.iter_employees():
            if rec.canonical_employee_id == canonical_id:
                return rec
        return None

    # ─── permission-aware extras (W7 정책 동일) ─────────────

    def fetch_extras(
        self,
        target_employee_id: str,
        viewer_employee_id: str,
        viewer_role_level: int,
        viewer_department: str | None,
        target_department: str | None,
    ) -> EmployeeExtras:
        # CSV 에는 trip/approval 데이터가 없다.
        # 권한 분기만 수행 — UI 가 PARTIAL/FULL 차이를 보일 수 있도록.
        if viewer_role_level >= 5 or viewer_employee_id == target_employee_id:
            permission = "FULL"
        elif (
            viewer_department
            and target_department
            and viewer_department == target_department
        ):
            permission = "PARTIAL"
        else:
            return EmployeeExtras(
                employee_id=target_employee_id,
                permission="DENIED",
                reason="권한 부족 — 같은 부서 또는 관리자 권한이 필요합니다.",
            )

        return EmployeeExtras(
            employee_id=target_employee_id,
            permission=permission,
            trips=[],  # CSV 미보유 — Sprint 2 에서 REST/LDAP 어댑터로 보강
            direct_reports=[],
            approvals=None,
        )


__all__ = ["CsvErpAdapter"]
