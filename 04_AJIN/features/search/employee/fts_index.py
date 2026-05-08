"""
SQLite FTS5 전문 검색 인덱스 — 사원 DB용
한글 유니코드 토크나이저(unicode61) 기반

사용법:
  python -m features.search.employee.fts_index build    # 인덱스 생성
  python -m features.search.employee.fts_index 품질보증  # 검색 테스트
"""
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("data/employees.db")


def create_fts_index(db_path: Path = DB_PATH) -> None:
    """
    employees 테이블의 FTS5 가상 테이블을 생성합니다.
    기존 인덱스가 있으면 재생성합니다.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DROP TABLE IF EXISTS employees_fts")

        conn.execute("""
            CREATE VIRTUAL TABLE employees_fts USING fts5(
                name,
                department,
                position,
                phone,
                email,
                extension,
                plant,
                tokenize='unicode61 remove_diacritics 0'
            )
        """)

        conn.execute("""
            INSERT INTO employees_fts(name, department, position, phone, email, extension, plant)
            SELECT
                COALESCE(name, ''),
                COALESCE(department, ''),
                COALESCE(position, ''),
                COALESCE(phone, ''),
                COALESCE(email, ''),
                COALESCE(extension, ''),
                COALESCE(plant, '')
            FROM employees
        """)

        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM employees_fts").fetchone()[0]
        logger.info(f"FTS5 인덱스 생성 완료: {count}건")
        print(f"FTS5 인덱스 생성 완료: {count}건")

    except Exception as e:
        logger.error(f"FTS5 인덱스 생성 실패: {e}")
        raise
    finally:
        conn.close()


def search_fts(
    query: str,
    db_path: Path = DB_PATH,
    limit: int = 20,
) -> list[dict]:
    """
    FTS5 전문 검색을 수행합니다.

    Args:
        query: 검색어 (예: "품질보증 과장", "홍길동")
        db_path: DB 파일 경로
        limit: 최대 결과 수

    Returns:
        검색 결과 딕셔너리 리스트
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        tokens = query.strip().split()
        if not tokens:
            return []

        # 각 토큰에 * 와일드카드 추가 (접두사 매칭)
        fts_terms = []
        for token in tokens:
            clean = token.replace('"', '""')
            fts_terms.append(f'"{clean}"*')

        # 모든 토큰이 매칭되어야 함 (AND 로직)
        fts_query = " AND ".join(fts_terms)

        rows = conn.execute("""
            SELECT e.*, rank
            FROM employees_fts fts
            JOIN employees e ON e.rowid = fts.rowid
            WHERE employees_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit)).fetchall()

        return [dict(row) for row in rows]

    except sqlite3.OperationalError as e:
        logger.warning(f"FTS5 검색 실패 (LIKE 폴백): {e}")
        return _fallback_like_search(query, conn, limit)
    finally:
        conn.close()


def _fallback_like_search(
    query: str,
    conn: sqlite3.Connection,
    limit: int,
) -> list[dict]:
    """FTS5 사용 불가 시 LIKE 기반 폴백 검색"""
    tokens = query.strip().split()
    conditions = []
    params = []

    for token in tokens:
        like_val = f"%{token}%"
        conditions.append(
            "(name LIKE ? OR department LIKE ? OR position LIKE ? "
            "OR email LIKE ? OR phone LIKE ?)"
        )
        params.extend([like_val] * 5)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    rows = conn.execute(
        f"SELECT * FROM employees WHERE {where_clause} LIMIT ?",
        params + [limit],
    ).fetchall()

    return [dict(row) for row in rows]


def rebuild_fts_index(db_path: Path = DB_PATH) -> int:
    """FTS5 인덱스를 재구축합니다. Returns: 인덱싱된 행 수"""
    create_fts_index(db_path)
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM employees_fts").fetchone()[0]
    conn.close()
    return count


def is_fts_available(db_path: Path = DB_PATH) -> bool:
    """FTS5 인덱스가 사용 가능한지 확인"""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT COUNT(*) FROM employees_fts")
        conn.close()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        create_fts_index()
    elif len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        results = search_fts(query)
        for r in results:
            print(f"  {r.get('name', '?')} | {r.get('department', '?')} | {r.get('position', '?')}")
        print(f"\n총 {len(results)}건")
    else:
        print("사용법:")
        print("  python -m features.search.employee.fts_index build    # 인덱스 생성")
        print("  python -m features.search.employee.fts_index 품질보증  # 검색 테스트")
