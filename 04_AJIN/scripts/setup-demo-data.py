#!/usr/bin/env python3
"""AJIN AI Assistant — 데모 데이터 생성 스크립트.

PUBLIC GitHub repo 에 사내 데이터를 commit 할 수 없으므로, clone 직후
빈 data/ 디렉토리를 가짜 데이터로 채워 즉시 실행 가능하게 한다.

생성 대상 (모두 가상):
  - data/auth.db                  — 시스템관리자 1명 + 일반 사용자 5명
  - data/employees.db             — 가짜 직원 30명 (5개 본부 × 6명)
  - data/compliance.db            — 공개 법규 샘플 5건 (산업안전보건법 등)
  - data/scenarios.db             — 시연 시나리오 5종
  - data/equipment/*.db           — 가짜 설비 10대 + 도면/오류이력 샘플
  - data/.jwt_secret              — 32-byte hex JWT 서명 키
  - data/knowledge_base/templates/ — 보고서 템플릿 6개 (.j2)
  - data/templates/{email,report,reference}/ — 빈 디렉토리

사용:
  python3 scripts/setup-demo-data.py
  python3 scripts/setup-demo-data.py --reset   # 기존 데이터 삭제 후 재생성
"""
from __future__ import annotations

import argparse
import os
import secrets
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"


def _connect(name: str) -> sqlite3.Connection:
    return sqlite3.connect(DATA / name)


def _run(conn: sqlite3.Connection, sql: str) -> None:
    for stmt in sql.strip().split(";\n"):
        s = stmt.strip()
        if s:
            conn.execute(s + ";")
    conn.commit()


def make_jwt_secret() -> None:
    """data/.jwt_secret — 32-byte hex 자동 생성."""
    p = DATA / ".jwt_secret"
    if p.exists():
        print(f"  [skip] {p.name} 이미 존재")
        return
    p.write_text(secrets.token_hex(32))
    p.chmod(0o600)
    print(f"  [✓] .jwt_secret 생성")


def make_auth_db() -> None:
    """data/auth.db — 시스템관리자 + 데모 사용자 6명."""
    p = DATA / "auth.db"
    if p.exists():
        print(f"  [skip] auth.db 이미 존재")
        return
    conn = _connect("auth.db")
    _run(conn, """
        CREATE TABLE IF NOT EXISTS users (
            employee_id TEXT PRIMARY KEY,
            username    TEXT NOT NULL,
            password_hash TEXT,
            role_level  INTEGER DEFAULT 1,
            role_name   TEXT,
            department  TEXT,
            position    TEXT,
            must_change_pw INTEGER DEFAULT 0
        )
    """)
    # 비밀번호는 setup 시 사용자가 직접 변경 — 여기선 placeholder hash
    PLACEHOLDER_HASH = "$2b$12$placeholder.placeholder.placeholder.placeholder"
    demo_users = [
        ("ADMIN001", "시스템관리자",   5, "sys_admin", "본사",   "관리자"),
        ("DEV001",   "개발팀원",       3, "developer", "본사",   "개발자"),
        ("QA001",    "품질보증팀원",    2, "user",      "천안1", "주임"),
        ("MFG001",   "생산팀원",       2, "user",      "천안2", "사원"),
        ("HR001",    "인사팀원",       4, "hr",        "본사",   "과장"),
        ("VIEWER01", "조회전용",      1, "viewer",    "본사",   "사원"),
    ]
    conn.executemany(
        "INSERT INTO users(employee_id, username, password_hash, role_level, role_name, department, position) "
        "VALUES (?, ?, '" + PLACEHOLDER_HASH + "', ?, ?, ?, ?)",
        [(u[0], u[1], u[2], u[3], u[4], u[5]) for u in demo_users],
    )
    conn.commit()
    conn.close()
    print(f"  [✓] auth.db 생성 ({len(demo_users)}명)")


def make_employees_db() -> None:
    """data/employees.db — 가짜 직원 30명."""
    p = DATA / "employees.db"
    if p.exists():
        print(f"  [skip] employees.db 이미 존재")
        return
    conn = _connect("employees.db")
    _run(conn, """
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            department  TEXT,
            position    TEXT,
            email       TEXT,
            phone       TEXT
        )
    """)
    departments = ["본사", "천안1", "천안2", "공장1", "공장2"]
    positions = ["사원", "주임", "대리", "과장", "차장", "부장"]
    rows = []
    for i in range(30):
        eid = f"DEMO{i+1:03d}"
        dept = departments[i % len(departments)]
        pos = positions[i % len(positions)]
        rows.append((
            eid,
            f"테스트{i+1:02d}",
            dept,
            pos,
            f"demo{i+1:03d}@example.com",
            f"010-0000-{i+1:04d}",
        ))
    conn.executemany(
        "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"  [✓] employees.db 생성 (30명)")


def make_compliance_db() -> None:
    """data/compliance.db — 공개 법규 샘플 5건."""
    p = DATA / "compliance.db"
    if p.exists():
        print(f"  [skip] compliance.db 이미 존재")
        return
    conn = _connect("compliance.db")
    _run(conn, """
        CREATE TABLE IF NOT EXISTS regulations (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            category    TEXT,
            article_no  TEXT,
            content     TEXT,
            source_url  TEXT,
            effective_date TEXT
        )
    """)
    samples = [
        ("REG001", "산업안전보건법 제38조 (안전조치)", "안전",
         "제38조", "사업주는 다음 각 호의 어느 하나에 해당하는 위험으로 인한 산업재해를 예방하기 위하여 필요한 조치를 하여야 한다...",
         "https://www.law.go.kr/법령/산업안전보건법", "2024-01-01"),
        ("REG002", "화학물질관리법 제13조 (취급기준)", "환경",
         "제13조", "유해화학물질을 취급하는 자는 환경부령으로 정하는 취급기준을 준수하여야 한다...",
         "https://www.law.go.kr/법령/화학물질관리법", "2024-03-15"),
        ("REG003", "근로기준법 제50조 (근로시간)", "노동",
         "제50조", "1주간의 근로시간은 휴게시간을 제외하고 40시간을 초과할 수 없다...",
         "https://www.law.go.kr/법령/근로기준법", "2024-01-01"),
        ("REG004", "개인정보보호법 제15조 (수집·이용)", "개인정보",
         "제15조", "개인정보처리자는 정보주체의 동의를 받아 개인정보를 수집할 수 있으며 그 수집 목적의 범위에서 이용할 수 있다...",
         "https://www.law.go.kr/법령/개인정보보호법", "2024-09-15"),
        ("REG005", "품질경영 및 공산품안전관리법 시행규칙 제8조", "품질",
         "제8조", "안전인증대상공산품의 제조업자 또는 수입업자는 안전인증을 받아야 한다...",
         "https://www.law.go.kr/법령/품질경영및공산품안전관리법", "2023-07-01"),
    ]
    conn.executemany(
        "INSERT INTO regulations VALUES (?, ?, ?, ?, ?, ?, ?)",
        samples,
    )
    conn.commit()
    conn.close()
    print(f"  [✓] compliance.db 생성 (5건)")


def make_scenarios_db() -> None:
    """data/scenarios.db — 시연 시나리오 5종."""
    p = DATA / "scenarios.db"
    if p.exists():
        print(f"  [skip] scenarios.db 이미 존재")
        return
    conn = _connect("scenarios.db")
    _run(conn, """
        CREATE TABLE IF NOT EXISTS scenarios (
            scenario_id TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            category    TEXT,
            description TEXT,
            steps_json  TEXT,
            active      INTEGER DEFAULT 1
        )
    """)
    samples = [
        ("DEMO_S1", "신입사원 온보딩 — Module C", "onboarding",
         "신규 입사자가 회사 규정·시스템·동료 정보를 AI 채팅으로 익히는 흐름", "[]"),
        ("DEMO_S2", "법규 준수 점검 — Module D", "compliance",
         "최근 변경된 산업안전보건법 조항이 우리 공정에 영향을 미치는지 분석", "[]"),
        ("DEMO_S3", "검사 보고서 자동 작성 — Module B", "draft",
         "설비 점검 결과를 입력하면 표준 보고서 양식으로 자동 작성", "[]"),
        ("DEMO_S4", "직원 검색 — Module A", "search",
         "이름·부서·직급으로 동료 정보 빠르게 찾기", "[]"),
        ("DEMO_S5", "설비 이상 진단 — Module F", "equipment",
         "설비 센서 데이터 기반 이상 패턴 사전 감지", "[]"),
    ]
    conn.executemany(
        "INSERT INTO scenarios VALUES (?, ?, ?, ?, ?, 1)",
        samples,
    )
    conn.commit()
    conn.close()
    print(f"  [✓] scenarios.db 생성 (5종)")


def make_equipment_dbs() -> None:
    """data/equipment/*.db — 가짜 설비 + 오류이력."""
    eq_dir = DATA / "equipment"
    eq_dir.mkdir(exist_ok=True)

    targets = ["drawings.db", "error_codes.db", "error_history.db",
               "inspection.db", "maintenance.db", "molds.db", "mold_lifecycle.db"]
    for name in targets:
        p = eq_dir / name
        if p.exists():
            print(f"  [skip] equipment/{name} 이미 존재")
            continue
        conn = sqlite3.connect(str(p))
        _run(conn, """
            CREATE TABLE IF NOT EXISTS records (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        rows = [(f"EQ{i:03d}", f"데모 레코드 {i}") for i in range(1, 11)]
        conn.executemany(
            "INSERT INTO records(equipment_id, description) VALUES (?, ?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"  [✓] equipment/{name} 생성 (10건)")


def make_template_dirs() -> None:
    """templates 디렉토리 골격 + 샘플 .j2 1개."""
    for sub in ["knowledge_base/templates", "templates/email", "templates/report", "templates/reference",
                "knowledge_base/glossary", "knowledge_base/sop", "knowledge_base/department_guides",
                "metadata", "scenarios", "facility_db", "regulation_ml",
                "intent_ml", "markov_ml", "mold_ml", "spc_ml", "spc_samples",
                "documents", "crawled", "fonts"]:
        d = DATA / sub
        d.mkdir(parents=True, exist_ok=True)

    sample_template = DATA / "knowledge_base" / "templates" / "demo_report_template.j2"
    if not sample_template.exists():
        sample_template.write_text(
            "# {{ title }}\n\n"
            "**작성자**: {{ author }}\n"
            "**일자**: {{ date }}\n\n"
            "## 요약\n{{ summary }}\n\n"
            "## 본문\n{{ body }}\n"
        )
        print(f"  [✓] knowledge_base/templates/demo_report_template.j2")


def reset() -> None:
    """기존 데모 데이터 삭제."""
    import shutil
    if DATA.exists():
        for child in DATA.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        print(f"[reset] {DATA} 의 데모 데이터 삭제")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="기존 데이터 삭제 후 재생성")
    args = parser.parse_args()

    DATA.mkdir(exist_ok=True)
    if args.reset:
        reset()

    print(f"\n▶ 데모 데이터 생성 — {DATA}")
    make_jwt_secret()
    make_auth_db()
    make_employees_db()
    make_compliance_db()
    make_scenarios_db()
    make_equipment_dbs()
    make_template_dirs()

    print(f"\n✓ 데모 데이터 셋업 완료 ({DATA})")
    print(f"  실 사내 데이터를 사용하려면 DBA 또는 데이터 담당자에게 문의하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
