"""AD/LDAP groupOf → AJIN role_name + role_level 매핑.

LDAP DN ('cn=TeamLead,ou=groups,dc=ajin,...') 의 cn 부분을 추출한 뒤 우선순위 매핑 표
(`GROUP_TO_ROLE`) 를 적용한다. 가장 높은 role_level 이 승.

HR_ADMIN 같은 일부 그룹은 departments 필터를 요구 (총무인사팀/ESG경영팀 소속이어야 적용).
부서 필터 불일치 시 해당 그룹은 무시되고 다음 우선순위 후보가 평가된다.

SAML 도 attribute (groups) 가 동일 형태로 들어오면 재사용 가능.
"""

from __future__ import annotations

from typing import Iterable, Optional

# role_name, role_level 은 auth.db roles 테이블의 기본 6종과 동기화.
# departments: 해당 그룹 매칭에 필요한 부서 집합 (None = 부서 무관).
GROUP_TO_ROLE: dict[str, dict] = {
    "IT-SystemAdmin": {"role_name": "SYS_ADMIN", "role_level": 5},
    "HR-Admin":       {"role_name": "HR_ADMIN",  "role_level": 4,
                       "departments": {"총무인사팀", "ESG경영팀"}},
    "TeamLead":       {"role_name": "TEAM_LEAD", "role_level": 3},
    "Manager":        {"role_name": "MANAGER",   "role_level": 2},
    "Employee":       {"role_name": "EMPLOYEE",  "role_level": 1},
    "External":       {"role_name": "GUEST",     "role_level": 0},
}

DEFAULT_ROLE: tuple[str, int] = ("EMPLOYEE", 1)


def extract_cn_from_dn(dn: str) -> str:
    """LDAP DN 의 'cn=...' RDN 값을 반환.

    예:
      'cn=TeamLead,ou=groups,dc=ajin,dc=co,dc=kr' → 'TeamLead'
      'CN=IT-SystemAdmin,OU=Groups,DC=ajin'        → 'IT-SystemAdmin'
      'TeamLead'                                    → 'TeamLead' (이미 cn)
      ''                                            → ''
    """
    if not dn:
        return ""
    # 콤마로 split — 첫 RDN 만 본다
    first = dn.split(",", 1)[0].strip()
    if "=" in first:
        key, val = first.split("=", 1)
        if key.strip().lower() == "cn":
            return val.strip()
        # cn 이 아닌 다른 RDN — 빈 문자열 (그룹 cn 만 처리)
        return ""
    # '=' 없으면 그 자체를 cn 으로 간주 (이미 simple name)
    return first


def map_groups_to_role(
    groups: Iterable[str],
    departments: Optional[Iterable[str]] = None,
) -> tuple[str, int]:
    """그룹 목록 + (옵션) 부서 집합 → (role_name, role_level).

    매칭 규칙:
      1. groups 각 항목에서 cn 추출 (DN 이면 parse, 아니면 그대로).
      2. GROUP_TO_ROLE 에 있는 cn 만 후보로 수집.
      3. departments 필터를 가진 그룹은 부서 교집합이 존재해야 후보 유지.
      4. 후보 중 role_level 최댓값을 가진 (role_name, role_level) 반환.
      5. 후보 0개면 DEFAULT_ROLE (EMPLOYEE, 1).
    """
    dept_set: set[str] = set(departments) if departments else set()
    candidates: list[tuple[str, int]] = []

    for raw in (groups or []):
        if not raw:
            continue
        cn = extract_cn_from_dn(raw)
        if not cn or cn not in GROUP_TO_ROLE:
            continue
        spec = GROUP_TO_ROLE[cn]
        required_depts = spec.get("departments")
        if required_depts:
            if not dept_set or dept_set.isdisjoint(required_depts):
                # 부서 필터 불일치 → skip
                continue
        candidates.append((spec["role_name"], int(spec["role_level"])))

    if not candidates:
        return DEFAULT_ROLE

    # role_level desc 정렬 후 1위
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0]
