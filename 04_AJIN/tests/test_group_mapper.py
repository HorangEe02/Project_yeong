"""v4.7 PR-E2 — group_mapper 단위 테스트."""

from __future__ import annotations

import pytest

from core.auth.group_mapper import (
    DEFAULT_ROLE,
    extract_cn_from_dn,
    map_groups_to_role,
)


# ── extract_cn_from_dn ────────────────────────────────────────────


def test_extract_cn_from_dn():
    assert extract_cn_from_dn("cn=TeamLead,ou=groups,dc=ajin,dc=co,dc=kr") == "TeamLead"


def test_extract_cn_from_complex_dn():
    # 대문자 CN/OU/DC 도 처리
    dn = "CN=IT-SystemAdmin,OU=Groups,OU=Security,DC=ajin,DC=co,DC=kr"
    assert extract_cn_from_dn(dn) == "IT-SystemAdmin"


def test_extract_cn_from_plain_name():
    # 이미 simple name 인 경우 그대로
    assert extract_cn_from_dn("Manager") == "Manager"


def test_extract_cn_from_empty():
    assert extract_cn_from_dn("") == ""
    assert extract_cn_from_dn(None) == ""  # type: ignore[arg-type]


def test_extract_cn_non_cn_rdn_returns_empty():
    # uid= 같은 다른 RDN 은 그룹 cn 이 아니므로 빈 문자열
    assert extract_cn_from_dn("uid=alice,ou=people,dc=ajin") == ""


# ── map_groups_to_role ────────────────────────────────────────────


def test_map_groups_to_role_sys_admin():
    groups = ["cn=IT-SystemAdmin,ou=groups,dc=ajin,dc=co,dc=kr"]
    assert map_groups_to_role(groups) == ("SYS_ADMIN", 5)


def test_map_groups_to_role_hr_admin_with_dept_filter():
    # 부서 일치 → HR_ADMIN
    groups = ["cn=HR-Admin,ou=groups,dc=ajin"]
    assert map_groups_to_role(groups, departments={"총무인사팀"}) == ("HR_ADMIN", 4)


def test_map_groups_to_role_hr_admin_dept_mismatch_falls_back():
    # 부서 불일치 → HR_ADMIN 후보 제외 → DEFAULT
    groups = ["cn=HR-Admin,ou=groups,dc=ajin"]
    assert map_groups_to_role(groups, departments={"품질보증팀"}) == DEFAULT_ROLE


def test_map_groups_to_role_hr_admin_no_dept_falls_back():
    # departments 미제공 → HR_ADMIN 후보 제외
    groups = ["cn=HR-Admin,ou=groups,dc=ajin"]
    assert map_groups_to_role(groups) == DEFAULT_ROLE


def test_map_groups_to_role_team_lead():
    groups = ["cn=TeamLead,ou=groups,dc=ajin,dc=co,dc=kr"]
    assert map_groups_to_role(groups) == ("TEAM_LEAD", 3)


def test_map_groups_to_role_unknown_defaults_employee():
    groups = ["cn=UnknownGroup,ou=groups,dc=ajin"]
    assert map_groups_to_role(groups) == DEFAULT_ROLE


def test_map_groups_to_role_priority_highest_wins():
    # 여러 그룹 동시 → 최상위 role_level 이 승
    groups = [
        "cn=Employee,ou=groups,dc=ajin",
        "cn=TeamLead,ou=groups,dc=ajin",
        "cn=IT-SystemAdmin,ou=groups,dc=ajin",
        "cn=Manager,ou=groups,dc=ajin",
    ]
    assert map_groups_to_role(groups) == ("SYS_ADMIN", 5)


def test_empty_groups_defaults_employee():
    assert map_groups_to_role([]) == DEFAULT_ROLE
    assert map_groups_to_role(None) == DEFAULT_ROLE  # type: ignore[arg-type]
