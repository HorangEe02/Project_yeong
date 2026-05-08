"""사내 인원 SQLite 데이터베이스

⚠️ 모든 인원 데이터는 시연용 가상 데이터입니다.
실제 아진산업 임직원과는 일체 관련이 없습니다.
"""

import sqlite3
from pathlib import Path

CREATE_EMPLOYEES_TABLE = """
CREATE TABLE IF NOT EXISTS employees (
    employee_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    name_en         TEXT,
    gender          TEXT CHECK(gender IN ('M', 'F')),
    position        TEXT NOT NULL,
    position_level  INTEGER NOT NULL,
    division        TEXT NOT NULL,
    department      TEXT NOT NULL,
    department_id   TEXT,
    role            TEXT DEFAULT '',
    email           TEXT,
    phone           TEXT,
    extension       TEXT,
    plant           TEXT DEFAULT '경산 본사',
    plant_id        TEXT DEFAULT 'PLANT-KS-HQ',
    hire_date       TEXT,
    is_active       INTEGER DEFAULT 1,
    is_team_leader  INTEGER DEFAULT 0,
    photo_url       TEXT DEFAULT '',
    overseas_assignment TEXT DEFAULT NULL,
    language_skills TEXT DEFAULT NULL
);
"""

# v1.6: 기존 DB에 해외파견 컬럼을 안전하게 추가하는 마이그레이션 쿼리
_MIGRATION_ADD_OVERSEAS = [
    "ALTER TABLE employees ADD COLUMN overseas_assignment TEXT DEFAULT NULL;",
    "ALTER TABLE employees ADD COLUMN language_skills TEXT DEFAULT NULL;",
]

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_emp_name ON employees(name);",
    "CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(department);",
    "CREATE INDEX IF NOT EXISTS idx_emp_division ON employees(division);",
    "CREATE INDEX IF NOT EXISTS idx_emp_plant ON employees(plant);",
    "CREATE INDEX IF NOT EXISTS idx_emp_position ON employees(position);",
    "CREATE INDEX IF NOT EXISTS idx_emp_extension ON employees(extension);",
]

POSITION_HIERARCHY = {
    "인턴": 0, "사원": 1, "주임": 2, "대리": 3, "과장": 4,
    "차장": 5, "부장": 6, "이사": 7, "상무": 8, "전무": 9, "부사장": 10,
}


class EmployeeDatabase:
    """사내 인원 데이터베이스"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "employees.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.execute(CREATE_EMPLOYEES_TABLE)
        for idx in CREATE_INDEXES:
            self.conn.execute(idx)
        # v1.6: 기존 DB에 해외파견 컬럼 안전 추가
        for migration in _MIGRATION_ADD_OVERSEAS:
            try:
                self.conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # 이미 컬럼이 존재하면 무시
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    # ── 개인 검색 ──

    def search_by_name(self, name: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM employees WHERE name LIKE ? AND is_active = 1 ORDER BY position_level DESC LIMIT ?",
            (f"%{name}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_by_extension(self, extension: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM employees WHERE extension = ? AND is_active = 1",
            (extension,),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_by_email(self, email: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM employees WHERE email LIKE ? AND is_active = 1",
            (f"%{email}%",),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_employee(self, employee_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── 부서 검색 ──

    def get_department_members(self, department: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM employees
               WHERE department = ? AND is_active = 1
               ORDER BY position_level DESC, hire_date ASC""",
            (department,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_team_leader(self, department: str) -> dict | None:
        row = self.conn.execute(
            """SELECT * FROM employees
               WHERE department = ? AND is_team_leader = 1 AND is_active = 1
               LIMIT 1""",
            (department,),
        ).fetchone()
        return dict(row) if row else None

    def get_division_members(self, division: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM employees
               WHERE division = ? AND is_active = 1
               ORDER BY department, position_level DESC""",
            (division,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── 통계 / 조직도 ──

    def get_department_headcount(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT division, department, COUNT(*) as headcount
               FROM employees WHERE is_active = 1
               GROUP BY division, department
               ORDER BY division, headcount DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_division_headcount(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT division, COUNT(*) as headcount
               FROM employees WHERE is_active = 1
               GROUP BY division ORDER BY headcount DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_plant_headcount(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT plant, COUNT(*) as headcount
               FROM employees WHERE is_active = 1
               GROUP BY plant ORDER BY headcount DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_position_distribution(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT position, COUNT(*) as headcount
               FROM employees WHERE is_active = 1
               GROUP BY position ORDER BY MIN(position_level)""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_gender_distribution(self) -> dict:
        rows = self.conn.execute(
            """SELECT gender, COUNT(*) as count
               FROM employees WHERE is_active = 1 GROUP BY gender""",
        ).fetchall()
        return {r["gender"]: r["count"] for r in rows}

    def get_org_tree(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT
                 e.division, e.department, COUNT(*) as headcount,
                 (SELECT name FROM employees e2
                  WHERE e2.department = e.department AND e2.is_team_leader = 1 AND e2.is_active = 1
                  LIMIT 1) as team_leader_name,
                 (SELECT position FROM employees e3
                  WHERE e3.department = e.department AND e3.is_team_leader = 1 AND e3.is_active = 1
                  LIMIT 1) as team_leader_position
               FROM employees e WHERE e.is_active = 1
               GROUP BY e.division, e.department
               ORDER BY e.division, headcount DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_total_headcount(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1").fetchone()
        return row[0]

    # ── 복합 검색 ──

    def search(self, name=None, department=None, division=None,
               position=None, plant=None, extension=None, limit=20) -> list[dict]:
        conditions = ["is_active = 1"]
        params = []
        if name:
            conditions.append("name LIKE ?"); params.append(f"%{name}%")
        if department:
            conditions.append("department LIKE ?"); params.append(f"%{department}%")
        if division:
            conditions.append("division LIKE ?"); params.append(f"%{division}%")
        if position:
            conditions.append("position = ?"); params.append(position)
        if plant:
            conditions.append("plant LIKE ?"); params.append(f"%{plant}%")
        if extension:
            conditions.append("extension = ?"); params.append(extension)

        where = " AND ".join(conditions)
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT * FROM employees WHERE {where} ORDER BY position_level DESC, department LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
