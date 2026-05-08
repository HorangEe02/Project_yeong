"""직원 검색 라우터.

v3.0: 인증 필수 + 가시성(visibility) 필터 적용
- 같은 부서/본부: FULL (모든 필드)
- 타 부서: PARTIAL (email 마스킹, phone 숨김)
- INACTIVE: HIDDEN (결과에서 제외)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

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

                items.append(EmployeeItem(
                    name=filtered.get("name", ""),
                    department=filtered.get("department", ""),
                    division=filtered.get("division", ""),
                    position=filtered.get("position", ""),
                    email=filtered.get("email", ""),
                    phone=filtered.get("phone", ""),
                    extension=filtered.get("extension", ""),
                    plant=filtered.get("plant", ""),
                ))

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
    user=Depends(get_current_user),
):
    """v3.6 — 전체 인사 DB 페이지네이션 조회.

    인사 검색 페이지 첫 진입 시 사용. 가시성 매트릭스 적용.
    이전에는 디자인 시스템 mock seed (24명 가상 인물) 를 첫 화면에 노출했지만,
    이는 실 DB 와 정합 안 됨 → 첫 화면도 실 DB 부분 집합 표시.

    - limit: 1~200 (기본 24, 인사 검색 페이지 그리드 6×4)
    - offset: 페이지네이션 시작 인덱스
    """
    from core.auth.visibility import determine_visibility, filter_employee_fields, VisibilityLevel

    # 입력 살균
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    import sqlite3
    from config import DATA_DIR

    db_path = DATA_DIR / "employees.db"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="employees.db 사용 불가")

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        # 본부/부서/직책 순으로 정렬 — 결정적 + UX 친화적
        # PARTIAL/HIDDEN 필터 후 limit 충족이 어려울 수 있어 candidate 를 limit×3 까지 페치.
        candidate_limit = max(limit * 3, 100)
        rows = conn.execute(
            "SELECT * FROM employees ORDER BY division, department, "
            "CASE position "
            "  WHEN '본부장' THEN 0 WHEN '이사' THEN 1 WHEN '상무' THEN 2 "
            "  WHEN '전무' THEN 3 WHEN '부장' THEN 4 WHEN '차장' THEN 5 "
            "  WHEN '과장' THEN 6 WHEN '대리' THEN 7 WHEN '주임' THEN 8 "
            "  WHEN '사원' THEN 9 ELSE 10 END, name "
            "LIMIT ? OFFSET ?",
            (candidate_limit, offset),
        ).fetchall()
        # 전체 카운트 (페이지네이션 메타용)
        total_in_db = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
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
        items.append(EmployeeItem(
            name=filtered.get("name", ""),
            department=filtered.get("department", ""),
            division=filtered.get("division", ""),
            position=filtered.get("position", ""),
            email=filtered.get("email", ""),
            phone=filtered.get("phone", ""),
            extension=filtered.get("extension", ""),
            plant=filtered.get("plant", ""),
        ))

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
        employees=items,
    )


@router.get("/by-department", response_model=EmployeeListResponse)
async def list_by_department(
    dept: str = "",
    division: str = "",
    user=Depends(get_current_user),
):
    """해당 부서(또는 본부)의 전체 인원을 반환한다 (limit 없음, max 500).

    가시성 필터 동일 적용:
      - HIDDEN → 결과에서 제외 (excluded 카운트)
      - PARTIAL → 필드 마스킹 (masked 카운트)
      - FULL → 그대로
    """
    from core.auth.visibility import determine_visibility, filter_employee_fields, VisibilityLevel

    if not dept and not division:
        raise HTTPException(status_code=400, detail="dept 또는 division 중 하나가 필요합니다.")

    # 슬림 모드 호환 — sqlite3 로 직접 조회
    # (features.search 패키지를 import하면 chromadb/rank_bm25 등 무거운 deps를 끔)
    import sqlite3
    from config import DATA_DIR

    db_path = DATA_DIR / "employees.db"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="employees.db 사용 불가")

    if dept:
        scope = "department"
        scope_name = dept
        sql = "SELECT * FROM employees WHERE department = ? ORDER BY position DESC, name"
        params: tuple[str, ...] = (dept,)
    else:
        scope = "division"
        scope_name = division
        sql = "SELECT * FROM employees WHERE division = ? ORDER BY department, position DESC, name"
        params = (division,)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
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
        items.append(EmployeeItem(
            name=filtered.get("name", ""),
            department=filtered.get("department", ""),
            division=filtered.get("division", ""),
            position=filtered.get("position", ""),
            email=filtered.get("email", ""),
            phone=filtered.get("phone", ""),
            extension=filtered.get("extension", ""),
            plant=filtered.get("plant", ""),
        ))

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
        employees=items,
    )


# ═══════════════════════════════════════════════════════════════
# GET /employee/org-tree — 본부 → 팀 트리 + 헤드카운트
# ═══════════════════════════════════════════════════════════════

@router.get("/org-tree", response_model=OrgTreeResponse)
async def get_org_tree(user=Depends(get_current_user)):
    """active 직원 기준 division → department 트리 + 카운트.

    프론트의 본부/팀 드롭다운 옵션으로 사용. mock ORG 와 무관하게 실 DB 기반.
    """
    import sqlite3
    from config import DATA_DIR

    db_path = DATA_DIR / "employees.db"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="employees.db 사용 불가")

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT division, department, COUNT(*) AS n
               FROM employees
               WHERE is_active = 1 AND division != '' AND department != ''
               GROUP BY division, department
               ORDER BY division, n DESC, department"""
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE is_active = 1"
        ).fetchone()[0]
        conn.close()
    except Exception as e:
        logger.error("org-tree 조회 실패: %s", e)
        raise HTTPException(status_code=503, detail=f"DB 조회 실패: {e}") from e

    # division 별로 묶어서 트리 빌드
    by_division: dict[str, list[TeamNode]] = {}
    division_count: dict[str, int] = {}
    for r in rows:
        div = r["division"]
        team = TeamNode(name=r["department"], headcount=int(r["n"]))
        by_division.setdefault(div, []).append(team)
        division_count[div] = division_count.get(div, 0) + int(r["n"])

    divisions = [
        DivisionNode(name=div, headcount=division_count[div], teams=teams)
        for div, teams in by_division.items()
    ]
    # 헤드카운트 큰 순으로 정렬
    divisions.sort(key=lambda d: d.headcount, reverse=True)

    return OrgTreeResponse(total=int(total or 0), divisions=divisions)
