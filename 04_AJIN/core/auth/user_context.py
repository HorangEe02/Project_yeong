"""
사용자 컨텍스트 — 로그인 사용자의 부서/직급/역할 정보를 각 기능에 주입

v3.0 Phase 0: 모든 기능 고도화의 선행 조건
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserContext:
    """현재 로그인한 사용자의 컨텍스트 정보"""
    user_id: int
    employee_id: str          # 사원번호
    name: str
    department: str           # 소속 부서 (예: "품질보증팀")
    division: str             # 소속 본부 (예: "품질본부")
    position: str             # 직급 (예: "과장")
    role: str                 # RBAC 역할 (예: "MANAGER")
    email: Optional[str] = None
    phone: Optional[str] = None
    site: Optional[str] = None  # 근무 사업장 (예: "경산 본사")

    # ── 편의 프로퍼티 ──

    @property
    def is_admin(self) -> bool:
        """SYS_ADMIN 또는 HR_ADMIN인지 확인"""
        return self.role in ("SYS_ADMIN", "HR_ADMIN")

    @property
    def is_leader(self) -> bool:
        """TEAM_LEAD 이상인지 확인"""
        return self.role in ("SYS_ADMIN", "HR_ADMIN", "TEAM_LEAD")

    @property
    def is_manager_or_above(self) -> bool:
        """MANAGER 이상인지 확인"""
        return self.role in ("SYS_ADMIN", "HR_ADMIN", "TEAM_LEAD", "MANAGER")

    @property
    def position_level(self) -> int:
        """직급을 숫자 레벨로 변환 (높을수록 고직급)"""
        return POSITION_LEVELS.get(self.position, 0)

    def has_min_position(self, min_position: str) -> bool:
        """최소 직급 이상인지 확인"""
        return self.position_level >= POSITION_LEVELS.get(min_position, 0)

    def to_prompt_context(self) -> str:
        """LLM 프롬프트에 주입할 사용자 정보 문자열"""
        return (
            f"[사용자 정보] 이름: {self.name} | 부서: {self.department} | "
            f"직급: {self.position} | 사업장: {self.site or '미지정'}"
        )


# ── 직급 레벨 매핑 ──
POSITION_LEVELS = {
    "사원": 1, "주임": 2, "대리": 3,
    "과장": 4, "차장": 5, "부장": 6,
    "이사": 7, "상무": 8, "전무": 9,
    "부사장": 10, "사장": 11,
}


# ── 부서 → 본부 매핑 (27개 부서) ──
DEPARTMENT_TO_DIVISION = {
    # 경영지원본부
    "내부감사팀": "경영지원본부",
    "재무팀": "경영지원본부",
    "회계팀": "경영지원본부",
    "원가기획팀": "경영지원본부",
    "총무인사팀": "경영지원본부",
    "ESG경영팀": "경영지원본부",
    "IT전략팀": "경영지원본부",
    # 영업본부
    "기술영업팀": "영업본부",
    "해외지원팀": "영업본부",
    "상생협력팀": "영업본부",
    # 구매본부
    "구매팀": "구매본부",
    "자재관리팀": "구매본부",
    # 생산본부
    "생산관리팀": "생산본부",
    "금형생산팀": "생산본부",
    "용기운영팀": "생산본부",
    "안전보건팀": "생산본부",
    # 기술본부
    "생산기술팀": "기술본부",
    "자동화기술팀": "기술본부",
    "FA사업팀": "기술본부",
    "플랜트사업팀": "기술본부",
    # 품질본부
    "품질보증팀": "품질본부",
    "품질경영팀": "품질본부",
    # 기술연구소
    "제품설계팀": "기술연구소",
    "공법계획팀": "기술연구소",
    "비전연구팀": "기술연구소",
    "바디선행개발팀": "기술연구소",
    "전장선행개발팀": "기술연구소",
    # 기타
    "부품개발팀": "기술본부",
    "기술교육원": "경영지원본부",
    # 레거시 호환 (v2.x에서 사용하던 본부명/부서명)
    "관리본부": "경영지원본부",
    "영업팀": "영업본부",
    "인사관리": "경영지원본부",
    "경영지원": "경영지원본부",
}


def get_user_context_from_session() -> Optional[UserContext]:
    """
    st.session_state에서 UserContext 객체를 생성하여 반환합니다.
    로그인하지 않은 경우 None을 반환합니다.

    session_state에 department/position이 없으면 auth.db에서 조회합니다.
    """
    import streamlit as st

    if not st.session_state.get("authenticated"):
        return None

    employee_id = st.session_state.get("user_employee_id", "")
    if not employee_id:
        return None

    name = st.session_state.get("user_name", "")
    role = st.session_state.get("user_role", "EMPLOYEE")

    # department/position이 세션에 있으면 사용, 없으면 DB 조회
    department = st.session_state.get("user_department", "")
    position = st.session_state.get("user_position", "")
    email = st.session_state.get("user_email", "")
    phone = st.session_state.get("user_phone", "")
    site = st.session_state.get("user_site", "")
    user_id = st.session_state.get("user_id", 0)

    if not department:
        # auth.db에서 부서/직급 조회
        _load_user_details_to_session(employee_id)
        department = st.session_state.get("user_department", "미지정")
        position = st.session_state.get("user_position", "사원")
        email = st.session_state.get("user_email", "")
        phone = st.session_state.get("user_phone", "")
        site = st.session_state.get("user_site", "경산 본사")
        user_id = st.session_state.get("user_id", 0)

    division = DEPARTMENT_TO_DIVISION.get(department, "기타")

    return UserContext(
        user_id=user_id,
        employee_id=employee_id,
        name=name,
        department=department,
        division=division,
        position=position or "사원",
        role=role,
        email=email or None,
        phone=phone or None,
        site=site or "경산 본사",
    )


def _load_user_details_to_session(employee_id: str) -> None:
    """auth.db에서 사용자 상세 정보를 조회하여 session_state에 캐싱합니다."""
    import streamlit as st

    try:
        from core.auth.database import get_auth_db
        conn = get_auth_db()
        row = conn.execute(
            """SELECT user_id, department, position, email, phone
               FROM users WHERE employee_id = ?""",
            (employee_id,),
        ).fetchone()
        conn.close()

        if row:
            st.session_state["user_id"] = row["user_id"]
            st.session_state["user_department"] = row["department"] or "미지정"
            st.session_state["user_position"] = row["position"] or "사원"
            st.session_state["user_email"] = row["email"] or ""
            st.session_state["user_phone"] = row["phone"] or ""

            # site 정보는 employees.db에서 조회
            _load_site_from_employees_db(employee_id)
        else:
            st.session_state["user_department"] = "미지정"
            st.session_state["user_position"] = "사원"

    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            f"사용자 상세 정보 조회 실패: {employee_id}"
        )
        st.session_state["user_department"] = "미지정"
        st.session_state["user_position"] = "사원"


def _load_site_from_employees_db(employee_id: str) -> None:
    """employees.db에서 사업장(site) 정보를 조회합니다."""
    import streamlit as st
    from pathlib import Path
    import sqlite3

    db_path = Path(__file__).parent.parent.parent / "data" / "employees.db"
    if not db_path.exists():
        st.session_state["user_site"] = "경산 본사"
        return

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT site FROM employees WHERE name = ? LIMIT 1",
            (st.session_state.get("user_name", ""),),
        ).fetchone()
        conn.close()

        st.session_state["user_site"] = row["site"] if row and row["site"] else "경산 본사"
    except Exception:
        st.session_state["user_site"] = "경산 본사"
