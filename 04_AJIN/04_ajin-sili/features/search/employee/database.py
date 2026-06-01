"""사내 인원 SQLite 데이터베이스.

Seed rows and real ERP/Admin rows can coexist. Operational filtering relies on
the shared ``data_class`` lineage columns rather than deleting demo data.
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
    language_skills TEXT DEFAULT NULL,
    is_synthetic INTEGER NOT NULL DEFAULT 1,
    source_system TEXT NOT NULL DEFAULT 'seed',
    canonical_employee_id TEXT DEFAULT NULL,
    data_class TEXT NOT NULL DEFAULT 'unknown',
    source_label TEXT DEFAULT '',
    source_updated_at TEXT DEFAULT ''
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
        # Sprint 1 P0 — canonical directory migration 0001
        # (is_synthetic / source_system / canonical_employee_id
        #  / headcount_snapshot / search_history)
        from core.directory import migrations as _dir_migrations
        _dir_migrations.apply_employees()

    def close(self):
        if self.conn:
            self.conn.close()

    # ── INSERT / UPSERT (Plan v3.7 — Module E 동기화) ──

    def add_employee(self, emp: dict) -> None:
        """employees.db 에 새 직원 INSERT OR REPLACE.

        Plan v3.7 — Module E (인사 관리) 에서 계정 생성 시 호출.
        호출자가 필드 매핑 보장. 누락 컬럼은 schema default 적용.
        필수 키: employee_id, name. 권장: position, position_level, division,
                department, email, phone, hire_date, is_active.
        """
        if not emp.get("employee_id") or not emp.get("name"):
            raise ValueError("add_employee: employee_id, name 필수")

        # 컬럼 화이트리스트 — schema 외 키 무시
        allowed = {
            "employee_id", "name", "name_en", "gender", "position", "position_level",
            "division", "department", "department_id", "role", "email", "phone",
            "extension", "plant", "plant_id", "hire_date", "is_active",
            "is_team_leader", "photo_url", "overseas_assignment", "language_skills",
            "is_synthetic", "source_system", "canonical_employee_id", "data_class",
            "source_label", "source_updated_at",
        }
        clean = {k: v for k, v in emp.items() if k in allowed}
        cols = list(clean.keys())
        placeholders = ",".join(["?"] * len(cols))
        self.conn.execute(
            f"INSERT OR REPLACE INTO employees ({','.join(cols)}) VALUES ({placeholders})",
            tuple(clean[c] for c in cols),
        )
        self.conn.commit()

        # Firebase reverse-sync를 대체하는 Postgres mirror. APP_DB_BACKEND=sqlite에서는 no-op.
        try:
            from features.search.employee.postgres_repository import upsert_employee
            upsert_employee(clean)
        except Exception as e:
            import logging
            logging.warning(f"[add_employee] Postgres mirror 호출 실패: {e}")

        # Plan v3.8 — ChromaDB incremental upsert (백그라운드, 사용자 응답 차단 X).
        # 임베딩 호출 0.5~2초 → daemon thread 로 fire-and-forget. 실패 silent skip.
        try:
            import threading
            from features.search.employee.semantic_search import index_employee_one
            threading.Thread(
                target=index_employee_one,
                args=(emp,),
                daemon=True,
            ).start()
        except Exception as e:
            import logging
            logging.warning(f"[add_employee] ChromaDB 비차단 호출 실패: {e}")

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


# ──────────────────────────────────────────────────────────────────
# Plan v3.7 — Firestore reverse-sync (Module E ↔ Module A 영속화)
# ──────────────────────────────────────────────────────────────────


def persist_employee_to_firestore(emp: dict) -> bool:
    """SQLite employees 변경을 Firestore 'employees' 컬렉션에 upsert.

    Cloud Run instance 재시작 시 employees.db 가 Dockerfile 의 baked-in
    원본으로 복원되는데, 그 후 부팅 lifespan 의 sync_employees_from_firestore
    함수가 Firestore → SQLite 로 다시 mirror 한다 (auth_users 패턴 동일).

    AUTH_BACKEND != 'firestore' (로컬 dev) 또는 firestore 클라이언트 실패 시
    silent skip — SQLite INSERT 자체는 이미 완료된 상태.
    """
    import os
    from core.feature_flags import firebase_writes_enabled

    if os.environ.get("AUTH_BACKEND", "").lower() != "firestore":
        return False
    if not firebase_writes_enabled():
        print("[employees] Firebase write 비활성 — Firestore employees upsert 스킵")
        return False
    if not emp.get("employee_id"):
        print(f"[employees] Firestore upsert 스킵 — employee_id 누락: {emp}")
        return False
    try:
        from google.cloud import firestore  # type: ignore
        db = firestore.Client()
        db.collection("employees").document(emp["employee_id"]).set(emp, merge=True)
        print(f"[employees] Firestore employees/{emp['employee_id']} upsert 완료")
        return True
    except Exception as e:
        print(f"[employees] Firestore upsert 실패 ({emp.get('employee_id')}): {e}")
        return False


def sync_employees_from_firestore_if_enabled(emp_db: "EmployeeDatabase") -> int:
    """AUTH_BACKEND=firestore 인 경우 Firestore 'employees' 컬렉션을
    employees.db 로 부팅 mirror. 인스턴스 재시작 후 새 계정 복원용.

    백엔드 lifespan (backend/main.py) 에서 EmployeeDatabase 초기화 직후 1회 호출.
    Returns: 동기화된 직원 수.
    """
    import os
    from core.feature_flags import firebase_read_fallback_enabled

    if os.environ.get("AUTH_BACKEND", "").lower() != "firestore":
        return 0
    if not firebase_read_fallback_enabled():
        print("[employees] Firestore read fallback 비활성 — employees mirror sync 스킵")
        return 0

    try:
        from google.cloud import firestore  # type: ignore
        db = firestore.Client()
    except Exception as e:
        print(f"[employees] Firestore 클라이언트 초기화 실패: {e}")
        return 0

    synced = 0
    try:
        for snap in db.collection("employees").stream():
            d = snap.to_dict() or {}
            emp_id = d.get("employee_id") or snap.id
            if not emp_id:
                continue
            d["employee_id"] = emp_id  # doc id 가 employee_id 가 아닐 수 있음
            try:
                emp_db.add_employee(d)
                synced += 1
            except Exception as e:
                print(f"[employees] {emp_id} 동기화 실패: {e}")
    except Exception as e:
        print(f"[employees] Firestore stream 실패: {e}")
        return synced

    return synced
