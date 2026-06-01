"""직원 검색 라우터.

v3.0: 인증 필수 + 가시성(visibility) 필터 적용
- 같은 부서/본부: FULL (모든 필드)
- 타 부서: PARTIAL (email 마스킹, phone 숨김)
- INACTIVE: HIDDEN (결과에서 제외)
"""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

from backend.dependencies import get_current_user, get_employee_engine
from backend.auth_middleware import log_api_access
from backend.schemas.employee import (
    DivisionNode,
    EmployeeItem,
    EmployeeListResponse,
    EmployeeSearchRequest,
    EmployeeSearchResponse,
    OrgTreeResponse,
    TeamNode,
)

router = APIRouter(prefix="/employee", tags=["employee"])


def _build_employee_item(filtered: dict) -> EmployeeItem:
    """Build an EmployeeItem while preserving source labeling fields.

    Args:
        filtered: Visibility-filtered employee row.

    Returns:
        EmployeeItem response model.
    """
    return EmployeeItem(
        name=filtered.get("name", ""),
        department=filtered.get("department", ""),
        division=filtered.get("division", ""),
        position=filtered.get("position", ""),
        email=filtered.get("email", ""),
        phone=filtered.get("phone", ""),
        extension=filtered.get("extension", ""),
        plant=filtered.get("plant", ""),
        is_synthetic=filtered.get("is_synthetic"),
        data_class=filtered.get("data_class") or "unknown",
        source_system=filtered.get("source_system") or "unknown",
        source_label=filtered.get("source_label") or "",
    )


def _source_counts(
    conn: sqlite3.Connection,
    where_sql: str = "1=1",
    params: tuple = (),
) -> dict[str, int]:
    """Compute real/synthetic/system counts for employee diagnostics.

    Args:
        conn: Open employees.db connection.
        where_sql: SQL predicate without ``WHERE``.
        params: Bind parameters for the predicate.

    Returns:
        Dict with ``real_count``, ``synthetic_count``, and ``system_count``.
    """
    row = conn.execute(
        f"""SELECT
              SUM(CASE WHEN data_class = 'real' THEN 1 ELSE 0 END) AS real_count,
              SUM(CASE WHEN data_class IN ('synthetic', 'demo') THEN 1 ELSE 0 END) AS synthetic_count,
              SUM(CASE WHEN data_class = 'system' THEN 1 ELSE 0 END) AS system_count
            FROM employees
            WHERE {where_sql}""",
        params,
    ).fetchone()
    if row is None:
        return {"real_count": 0, "synthetic_count": 0, "system_count": 0}
    return {
        "real_count": int(row["real_count"] or 0),
        "synthetic_count": int(row["synthetic_count"] or 0),
        "system_count": int(row["system_count"] or 0),
    }


def _role_level_of(user) -> int:
    """Resolve a numeric role level from user context.

    Args:
        user: Authenticated user context.

    Returns:
        int: Numeric RBAC level. Unknown roles fail closed to 0.
    """
    raw = getattr(user, "role_level", None)
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    try:
        from core.auth.rbac import get_role_level

        return int(get_role_level(str(getattr(user, "role", "") or "")))
    except Exception:
        return 0


@router.post("/search", response_model=EmployeeSearchResponse)
async def search_employee(
    req: EmployeeSearchRequest,
    engine=Depends(get_employee_engine),
    user=Depends(get_current_user),
):
    """자연어로 직원을 검색한다. (인증 필수 + 가시성 필터)"""
    try:
        from core.auth.visibility import determine_visibility, filter_employee_fields, VisibilityLevel

        result = engine.search(req.query)

        items = []
        raw_results = result.get("results", [])
        if isinstance(raw_results, list):
            for r in raw_results:
                if not isinstance(r, dict):
                    continue

                # 가시성 판단
                emp_dept = r.get("department", "")
                emp_role = r.get("role", "EMPLOYEE")
                vis = determine_visibility(user, emp_dept, emp_role)

                # HIDDEN → 제외
                if vis == VisibilityLevel.HIDDEN:
                    continue

                # PARTIAL → 필드 마스킹
                filtered = filter_employee_fields(r, vis)

                items.append(_build_employee_item(filtered))

        # 감사 로깅
        log_api_access(
            endpoint="/api/employee/search",
            method="POST",
            status_code=200,
            detail=f"query={req.query}, results={len(items)}",
            user=user,
        )

        return EmployeeSearchResponse(
            mode=result.get("mode", ""),
            results=items,
            message=result.get("message", ""),
            formatted_markdown=result.get("formatted", ""),
            total=len(items),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("search_employee error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════
# GET /employee/by-department — 부서/본부 단위 전체 인원
# ═══════════════════════════════════════════════════════════════

@router.get("/list", response_model=EmployeeListResponse)
async def list_employees_paginated(
    limit: int = 24,
    offset: int = 0,
    include_synthetic: bool | None = Query(
        None,
        description="None이면 AJIN_DATA_CLASS_MODE/AJIN_EXCLUDE_SYNTHETIC 정책을 따른다.",
    ),
    user=Depends(get_current_user),
):
    """v3.6 — 전체 인사 DB 페이지네이션 조회.

    인사 검색 페이지 첫 진입 시 사용. 가시성 매트릭스 적용.
    이전에는 디자인 시스템 mock seed (24명 가상 인물) 를 첫 화면에 노출했지만,
    이는 실 DB 와 정합 안 됨 → 첫 화면도 실 DB 부분 집합 표시.

    - limit: 1~200 (기본 24, 인사 검색 페이지 그리드 6×4)
    - offset: 페이지네이션 시작 인덱스
    """
    from core.data_lineage import data_class_predicate
    from core.auth.visibility import determine_visibility, filter_employee_fields, VisibilityLevel

    # 입력 살균
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    from config import DATA_DIR

    db_path = DATA_DIR / "employees.db"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="employees.db 사용 불가")

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        data_filter = data_class_predicate(
            include_non_real=include_synthetic,
            fallback_is_synthetic_column="is_synthetic",
        )
        # 본부/부서/직책 순으로 정렬 — 결정적 + UX 친화적
        # PARTIAL/HIDDEN 필터 후 limit 충족이 어려울 수 있어 candidate 를 limit×3 까지 페치.
        candidate_limit = max(limit * 3, 100)
        rows = conn.execute(
            f"SELECT * FROM employees WHERE {data_filter} ORDER BY division, department, "
            "CASE position "
            "  WHEN '본부장' THEN 0 WHEN '이사' THEN 1 WHEN '상무' THEN 2 "
            "  WHEN '전무' THEN 3 WHEN '부장' THEN 4 WHEN '차장' THEN 5 "
            "  WHEN '과장' THEN 6 WHEN '대리' THEN 7 WHEN '주임' THEN 8 "
            "  WHEN '사원' THEN 9 ELSE 10 END, name "
            "LIMIT ? OFFSET ?",
            (candidate_limit, offset),
        ).fetchall()
        # 전체 카운트 (페이지네이션 메타용)
        total_in_db = conn.execute(f"SELECT COUNT(*) FROM employees WHERE {data_filter}").fetchone()[0]
        counts = _source_counts(conn)
        conn.close()
        members = [dict(r) for r in rows]
    except Exception as e:
        logger.error("employees.db 조회 실패: %s", e)
        raise HTTPException(status_code=503, detail=f"DB 조회 실패: {e}") from e

    items: list[EmployeeItem] = []
    masked_n = 0
    excluded_n = 0

    for r in members:
        emp_dept = r.get("department", "")
        emp_role = r.get("role", "EMPLOYEE")
        vis = determine_visibility(user, emp_dept, emp_role)

        if vis == VisibilityLevel.HIDDEN:
            excluded_n += 1
            continue
        if vis == VisibilityLevel.PARTIAL:
            masked_n += 1

        filtered = filter_employee_fields(r, vis)
        items.append(_build_employee_item(filtered))

        if len(items) >= limit:
            break

    log_api_access(
        endpoint="/api/employee/list",
        method="GET",
        status_code=200,
        detail=f"limit={limit}, offset={offset}, total_in_db={total_in_db}, "
               f"returned={len(items)}, masked={masked_n}, excluded={excluded_n}",
        user=user,
    )

    return EmployeeListResponse(
        scope="all",
        name=f"전체 (DB {total_in_db}명 중 {len(items)}명 표시)",
        total=total_in_db,  # DB 총 인원 (UI 의 "전체 N명" 표시용)
        masked=masked_n,
        excluded=excluded_n,
        **counts,
        employees=items,
    )


@router.get("/by-department", response_model=EmployeeListResponse)
async def list_by_department(
    dept: str = "",
    division: str = "",
    include_synthetic: bool | None = Query(
        None,
        description="None이면 AJIN_DATA_CLASS_MODE/AJIN_EXCLUDE_SYNTHETIC 정책을 따른다.",
    ),
    user=Depends(get_current_user),
):
    """해당 부서(또는 본부)의 전체 인원을 반환한다 (limit 없음, max 500).

    가시성 필터 동일 적용:
      - HIDDEN → 결과에서 제외 (excluded 카운트)
      - PARTIAL → 필드 마스킹 (masked 카운트)
      - FULL → 그대로
    """
    from core.data_lineage import data_class_predicate
    from core.auth.visibility import determine_visibility, filter_employee_fields, VisibilityLevel

    if not dept and not division:
        raise HTTPException(status_code=400, detail="dept 또는 division 중 하나가 필요합니다.")

    # 슬림 모드 호환 — sqlite3 로 직접 조회
    # (features.search 패키지를 import하면 chromadb/rank_bm25 등 무거운 deps를 끔)
    from config import DATA_DIR

    db_path = DATA_DIR / "employees.db"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="employees.db 사용 불가")

    data_filter = data_class_predicate(
        include_non_real=include_synthetic,
        fallback_is_synthetic_column="is_synthetic",
    )
    if dept:
        scope = "department"
        scope_name = dept
        sql = f"SELECT * FROM employees WHERE department = ? AND {data_filter} ORDER BY position DESC, name"
        params: tuple[str, ...] = (dept,)
        count_where = "department = ?"
    else:
        scope = "division"
        scope_name = division
        sql = f"SELECT * FROM employees WHERE division = ? AND {data_filter} ORDER BY department, position DESC, name"
        params = (division,)
        count_where = "division = ?"

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        counts = _source_counts(conn, count_where, params)
        conn.close()
        members = [dict(r) for r in rows]
    except Exception as e:
        logger.error("employees.db 조회 실패: %s", e)
        raise HTTPException(status_code=503, detail=f"DB 조회 실패: {e}") from e

    # 안전장치 — 너무 많은 경우 캡 (실제 부서는 50명 이하라 비상시만 동작)
    if len(members) > 500:
        members = members[:500]

    items: list[EmployeeItem] = []
    masked_n = 0
    excluded_n = 0

    for r in members:
        if not isinstance(r, dict):
            continue

        emp_dept = r.get("department", "")
        emp_role = r.get("role", "EMPLOYEE")
        vis = determine_visibility(user, emp_dept, emp_role)

        if vis == VisibilityLevel.HIDDEN:
            excluded_n += 1
            continue
        if vis == VisibilityLevel.PARTIAL:
            masked_n += 1

        filtered = filter_employee_fields(r, vis)
        items.append(_build_employee_item(filtered))

    log_api_access(
        endpoint="/api/employee/by-department",
        method="GET",
        status_code=200,
        detail=f"{scope}={scope_name}, total={len(items)}, masked={masked_n}, excluded={excluded_n}",
        user=user,
    )

    return EmployeeListResponse(
        scope=scope,
        name=scope_name,
        total=len(items),
        masked=masked_n,
        excluded=excluded_n,
        **counts,
        employees=items,
    )


# ═══════════════════════════════════════════════════════════════
# GET /employee/org-tree — 본부 → 팀 트리 + 헤드카운트
# ═══════════════════════════════════════════════════════════════

@router.get("/org-tree", response_model=OrgTreeResponse)
async def get_org_tree(
    include_synthetic: bool | None = Query(
        None,
        description="None이면 AJIN_DATA_CLASS_MODE/AJIN_EXCLUDE_SYNTHETIC 정책을 따른다.",
    ),
    user=Depends(get_current_user),
):
    """active 직원 기준 division → department 트리 + 카운트.

    프론트의 본부/팀 드롭다운 옵션으로 사용. mock ORG 와 무관하게 실 DB 기반.
    """
    from core.data_lineage import data_class_predicate
    from config import DATA_DIR

    db_path = DATA_DIR / "employees.db"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="employees.db 사용 불가")

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        data_filter = data_class_predicate(
            include_non_real=include_synthetic,
            alias="e",
            fallback_is_synthetic_column="is_synthetic",
        )
        rows = conn.execute(
            f"""SELECT division,
                       department,
                       COUNT(*) AS n,
                       SUM(CASE WHEN data_class = 'real' THEN 1 ELSE 0 END) AS real_count,
                       SUM(CASE WHEN data_class IN ('synthetic', 'demo') THEN 1 ELSE 0 END) AS synthetic_count
               FROM employees e
               WHERE is_active = 1 AND division != '' AND department != ''
                 AND {data_filter}
               GROUP BY division, department
               ORDER BY division, n DESC, department"""
        ).fetchall()
        total_row = conn.execute(
            f"""SELECT COUNT(*) AS total,
                       SUM(CASE WHEN data_class = 'real' THEN 1 ELSE 0 END) AS real_count,
                       SUM(CASE WHEN data_class IN ('synthetic', 'demo') THEN 1 ELSE 0 END) AS synthetic_count,
                       SUM(CASE WHEN data_class = 'system' THEN 1 ELSE 0 END) AS system_count
                FROM employees e
                WHERE is_active = 1 AND {data_filter}"""
        ).fetchone()
        conn.close()
    except Exception as e:
        logger.error("org-tree 조회 실패: %s", e)
        raise HTTPException(status_code=503, detail=f"DB 조회 실패: {e}") from e

    # division 별로 묶어서 트리 빌드
    by_division: dict[str, list[TeamNode]] = {}
    division_count: dict[str, int] = {}
    for r in rows:
        div = r["division"]
        team = TeamNode(
            name=r["department"],
            headcount=int(r["n"]),
            real_count=int(r["real_count"] or 0),
            synthetic_count=int(r["synthetic_count"] or 0),
        )
        by_division.setdefault(div, []).append(team)
        division_count[div] = division_count.get(div, 0) + int(r["n"])

    divisions = [
        DivisionNode(
            name=div,
            headcount=division_count[div],
            real_count=sum(t.real_count for t in teams),
            synthetic_count=sum(t.synthetic_count for t in teams),
            teams=teams,
        )
        for div, teams in by_division.items()
    ]
    # 헤드카운트 큰 순으로 정렬
    divisions.sort(key=lambda d: d.headcount, reverse=True)

    total_count = int(total_row["total"] or 0) if total_row is not None else 0
    real_count = int(total_row["real_count"] or 0) if total_row is not None else 0
    synthetic_count = int(total_row["synthetic_count"] or 0) if total_row is not None else 0
    system_count = int(total_row["system_count"] or 0) if total_row is not None else 0
    return OrgTreeResponse(
        total=total_count,
        real_count=real_count,
        synthetic_count=synthetic_count,
        system_count=system_count,
        divisions=divisions,
    )


# ═══════════════════════════════════════════════════════════════
# W7 — GET /employee/{employee_id}/extras
# ERP/HRIS 어댑터를 통해 출장이력 / 직속부하 / 결재 현황 등 부가 정보 반환.
# 권한 정책은 ErpAdapter 가 결정 (role_level + dept 컨텍스트).
# ═══════════════════════════════════════════════════════════════

@router.get("/{employee_id}/extras")
async def get_employee_extras(
    employee_id: str,
    user=Depends(get_current_user),
):
    """W7 — 권한 기반 강화 정보 (출장 / 직속부하 / 결재).

    실 ERP 연동 시 features/search/adapters/erp_adapter.py 의
    `get_erp_adapter()` 를 RealErpAdapter 로 교체하면 동작 유지.
    """
    from features.search.adapters.erp_adapter import get_erp_adapter

    # target 부서 추정 — employee_id 가 'DEPT-001' 형식이면 prefix 가 부서코드.
    target_dept = employee_id.split("-")[0] if "-" in employee_id else None

    viewer_role_level = _role_level_of(user)

    adapter = get_erp_adapter()
    extras = adapter.fetch_extras(
        target_employee_id=employee_id,
        viewer_employee_id=user.employee_id,
        viewer_role_level=viewer_role_level,
        viewer_department=user.department,
        target_department=target_dept,
    )

    log_api_access(
        endpoint="/employee/{id}/extras",
        method="GET",
        status_code=200,
        detail=f"target={employee_id} permission={extras.permission}",
        user=user,
    )

    return extras.to_dict()
