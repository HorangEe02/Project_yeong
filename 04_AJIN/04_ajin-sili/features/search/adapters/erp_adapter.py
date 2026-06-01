"""ERP / HRIS adapter — W7 인터페이스 lock-in.

실제 사내 ERP / HRIS 연동은 PoC 단계 별도 트랙. 본 모듈은 인터페이스를 확정하고
시연 가능한 mock 구현을 제공한다. 라우터/UI 는 인터페이스에만 의존하므로
실 연동 전환 시 `MockErpAdapter` → `RealErpAdapter` 교체만으로 동작 유지.

권한 정책 (W7 기본 규칙):
- role_level >= 5 (SYS_ADMIN / HR_ADMIN) → 전체 항목 노출
- 직속 상관 (manager_of) → 출장이력 / 직속부하 노출, 결재 현황 노출
- 같은 본부/부서 동료 → 부분 노출 (직속부하만)
- 그 외 → 권한 부족 (빈 응답 + reason)
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Iterator, Optional


# ─────────────────────────────────────────────────────────────
# Domain types
# ─────────────────────────────────────────────────────────────


@dataclass
class TripRecord:
    """출장 이력 한 건."""

    trip_id: str
    destination: str
    purpose: str
    started_on: str  # ISO YYYY-MM-DD
    ended_on: str
    cost_krw: int


@dataclass
class DirectReport:
    """직속 부하 한 명."""

    employee_id: str
    name: str
    position: str
    department: str


@dataclass
class ApprovalSummary:
    """결재 현황 요약."""

    pending: int
    approved_30d: int
    rejected_30d: int


@dataclass
class EmployeeExtras:
    """공개 가능한 인사 부가 정보 묶음."""

    employee_id: str
    permission: str  # 'FULL' | 'PARTIAL' | 'DENIED'
    reason: str = ''
    trips: list[TripRecord] = field(default_factory=list)
    direct_reports: list[DirectReport] = field(default_factory=list)
    approvals: ApprovalSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # asdict 가 dataclass 를 dict 로 풀어버리므로 재포장 필요 없음
        return d


@dataclass
class EmployeeRecord:
    """ERP/HRIS 가 발행하는 직원 마스터 한 건.

    Sprint 1 P0 (Feature A §4.1, plan §4.2) — sync_runner 가 이 레코드를
    employees 테이블에 upsert. `canonical_employee_id` 는 ERP 측 PK,
    내부 `employee_id` 와 다를 수 있다.
    """

    canonical_employee_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    division: Optional[str] = None
    position: Optional[str] = None
    position_level: Optional[int] = None
    plant: Optional[str] = None
    hire_date: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────
# Adapter interface
# ─────────────────────────────────────────────────────────────


class ErpAdapter(ABC):
    """ERP/HRIS 어댑터 추상 인터페이스."""

    @abstractmethod
    def fetch_extras(
        self,
        target_employee_id: str,
        viewer_employee_id: str,
        viewer_role_level: int,
        viewer_department: str | None,
        target_department: str | None,
    ) -> EmployeeExtras:
        """뷰어의 권한 컨텍스트를 받아 부가 정보를 반환.

        실제 ERP 연동에서는 여기에 사내망 API 호출 + 토큰 검증이 들어간다.
        """

    @abstractmethod
    def fetch_employee_by_canonical_id(
        self, canonical_id: str
    ) -> Optional[EmployeeRecord]:
        """ERP 측 정식 ID로 단건 조회. 미존재 시 None.

        Sprint 1 P0 — sync_runner 가 incremental upsert 시 사용.
        """

    @abstractmethod
    def iter_employees(self) -> Iterator[EmployeeRecord]:
        """ERP 가 보유한 모든 직원 마스터 yield.

        Sprint 1 P0 — sync_runner 가 nightly full sync 시 사용.
        Mock 어댑터는 빈 iterator 반환 (실 데이터 없음).
        """


# ─────────────────────────────────────────────────────────────
# Mock implementation
# ─────────────────────────────────────────────────────────────


class MockErpAdapter(ErpAdapter):
    """시연용 mock — 권한 분기와 데이터 포맷이 실 연동과 동일하다."""

    def fetch_extras(
        self,
        target_employee_id: str,
        viewer_employee_id: str,
        viewer_role_level: int,
        viewer_department: str | None,
        target_department: str | None,
    ) -> EmployeeExtras:
        # 권한 판정
        if viewer_role_level >= 5:
            permission = 'FULL'
        elif viewer_department and target_department and viewer_department == target_department:
            permission = 'PARTIAL'
        elif viewer_employee_id == target_employee_id:
            permission = 'FULL'  # 본인은 본인 정보 전체 조회
        else:
            return EmployeeExtras(
                employee_id=target_employee_id,
                permission='DENIED',
                reason='권한 부족 — 같은 부서 또는 관리자 권한이 필요합니다.',
            )

        # 시연용 mock 데이터
        trips: list[TripRecord] = []
        direct_reports: list[DirectReport] = []
        approvals: ApprovalSummary | None = None

        if permission == 'FULL':
            trips = [
                TripRecord(
                    trip_id=f'TRIP-{target_employee_id}-001',
                    destination='조지아 (HMGMA)',
                    purpose='EWP/CCH 라인 시운전 입회',
                    started_on='2026-03-12',
                    ended_on='2026-03-19',
                    cost_krw=4_820_000,
                ),
                TripRecord(
                    trip_id=f'TRIP-{target_employee_id}-002',
                    destination='경주 외동공장',
                    purpose='SQ 인증 사전 점검',
                    started_on='2026-04-05',
                    ended_on='2026-04-05',
                    cost_krw=120_000,
                ),
            ]
            approvals = ApprovalSummary(pending=3, approved_30d=18, rejected_30d=1)

        # PARTIAL 또는 FULL 모두 직속부하는 표시
        direct_reports = [
            DirectReport(
                employee_id=f'{target_department or "DEPT"}-101',
                name='김철수',
                position='대리',
                department=target_department or '—',
            ),
            DirectReport(
                employee_id=f'{target_department or "DEPT"}-102',
                name='이영희',
                position='주임',
                department=target_department or '—',
            ),
        ]

        return EmployeeExtras(
            employee_id=target_employee_id,
            permission=permission,
            trips=trips,
            direct_reports=direct_reports,
            approvals=approvals,
        )

    def fetch_employee_by_canonical_id(
        self, canonical_id: str
    ) -> Optional[EmployeeRecord]:
        # Mock 은 실 데이터셋이 없으므로 None 반환.
        return None

    def iter_employees(self) -> Iterator[EmployeeRecord]:
        # Mock 은 빈 iterator — sync_runner 가 안전하게 no-op.
        if False:
            yield  # pragma: no cover — 명시적 generator 마커
        return


# ─────────────────────────────────────────────────────────────
# Singleton accessor (라우터/서비스에서 주입 받기 쉽게)
# ─────────────────────────────────────────────────────────────

_default_adapter: ErpAdapter | None = None


def get_erp_adapter() -> ErpAdapter:
    """기본 어댑터 반환. AJIN_ERP_MODE env 로 모드 분기.

    Sprint 1 P0 (Feature A §4.1 / plan §4.2):
      - mock (default): MockErpAdapter
      - csv: CsvErpAdapter (lazy import — 부재 시 즉시 에러)
    Sprint 2 추가 예정: ldap, rest.
    """
    global _default_adapter
    if _default_adapter is not None:
        return _default_adapter

    mode = os.getenv("AJIN_ERP_MODE", "mock").lower()
    if mode == "mock":
        _default_adapter = MockErpAdapter()
    elif mode == "csv":
        from features.search.adapters.csv_erp_adapter import CsvErpAdapter
        _default_adapter = CsvErpAdapter()
    else:
        raise ValueError(
            f"unsupported AJIN_ERP_MODE={mode!r}. supported: mock | csv"
        )
    return _default_adapter


def reset_erp_adapter() -> None:
    """싱글톤 재설정 — 테스트/CLI 에서 env 변경 후 재바인딩용."""
    global _default_adapter
    _default_adapter = None
