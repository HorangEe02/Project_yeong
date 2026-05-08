"""
인력 통계 분석 엔진
- 부서별/직급별/사업장별/성별 인원 분포
- 근속연수 분석
- 본부별 인력 구성 비교
- 본부 x 직급 히트맵
"""

import sqlite3
from datetime import datetime, date
from typing import Dict, List
from collections import defaultdict
from pathlib import Path

DB_PATH = Path("data/employees.db")

POSITION_ORDER = {
    "전무": 1, "이사": 2, "상무": 3, "부장": 4, "차장": 5,
    "과장": 6, "대리": 7, "주임": 8, "사원": 9, "인턴": 10,
}


def _connect(db_path: str = None):
    p = db_path or str(DB_PATH)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def get_summary_stats(db_path: str = None) -> Dict:
    """전체 요약 통계"""
    conn = _connect(db_path)
    total = conn.execute(
        "SELECT COUNT(*) FROM employees WHERE is_active=1 OR is_active IS NULL"
    ).fetchone()[0]
    depts = conn.execute(
        "SELECT COUNT(DISTINCT department) FROM employees WHERE is_active=1 OR is_active IS NULL"
    ).fetchone()[0]
    divs = conn.execute(
        "SELECT COUNT(DISTINCT division) FROM employees WHERE division IS NOT NULL AND (is_active=1 OR is_active IS NULL)"
    ).fetchone()[0]
    plants = conn.execute(
        "SELECT COUNT(DISTINCT plant) FROM employees WHERE plant IS NOT NULL AND (is_active=1 OR is_active IS NULL)"
    ).fetchone()[0]
    leaders = conn.execute(
        "SELECT COUNT(*) FROM employees WHERE is_team_leader=1"
    ).fetchone()[0]
    conn.close()
    return {"total": total, "departments": depts, "divisions": divs, "plants": plants, "leaders": leaders}


def get_headcount_by_division(db_path: str = None) -> List[Dict]:
    """본부별 인원수"""
    conn = _connect(db_path)
    cursor = conn.execute("""
        SELECT division, COUNT(*) as count, COUNT(DISTINCT department) as dept_count
        FROM employees WHERE (is_active=1 OR is_active IS NULL) AND division IS NOT NULL
        GROUP BY division ORDER BY count DESC
    """)
    results = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return results


def get_headcount_by_department(db_path: str = None) -> List[Dict]:
    """부서별 인원수"""
    conn = _connect(db_path)
    cursor = conn.execute("""
        SELECT department, division, COUNT(*) as count
        FROM employees WHERE is_active=1 OR is_active IS NULL
        GROUP BY department ORDER BY count DESC
    """)
    results = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return results


def get_headcount_by_position(db_path: str = None) -> List[Dict]:
    """직급별 인원수 (직급 순서 정렬)"""
    conn = _connect(db_path)
    cursor = conn.execute("""
        SELECT position, COUNT(*) as count
        FROM employees WHERE is_active=1 OR is_active IS NULL
        GROUP BY position
    """)
    results = [dict(r) for r in cursor.fetchall()]
    conn.close()
    results.sort(key=lambda x: POSITION_ORDER.get(x["position"], 99))
    return results


def get_headcount_by_plant(db_path: str = None) -> List[Dict]:
    """사업장별 인원수"""
    conn = _connect(db_path)
    cursor = conn.execute("""
        SELECT plant, COUNT(*) as count
        FROM employees WHERE (is_active=1 OR is_active IS NULL) AND plant IS NOT NULL
        GROUP BY plant ORDER BY count DESC
    """)
    results = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return results


def get_gender_distribution(db_path: str = None) -> Dict[str, int]:
    """성별 분포"""
    conn = _connect(db_path)
    cursor = conn.execute("""
        SELECT gender, COUNT(*) as count
        FROM employees WHERE is_active=1 OR is_active IS NULL
        GROUP BY gender
    """)
    results = {row["gender"]: row["count"] for row in cursor.fetchall()}
    conn.close()
    return results


def get_tenure_distribution(db_path: str = None) -> List[Dict]:
    """근속연수 분포"""
    conn = _connect(db_path)
    cursor = conn.execute("""
        SELECT hire_date FROM employees
        WHERE (is_active=1 OR is_active IS NULL) AND hire_date IS NOT NULL
    """)
    today = date.today()
    buckets = {"1년 미만": 0, "1~3년": 0, "3~5년": 0, "5~10년": 0, "10년 이상": 0}

    for row in cursor.fetchall():
        try:
            hire = datetime.strptime(row["hire_date"], "%Y-%m-%d").date()
            years = (today - hire).days / 365.25
            if years < 1:
                buckets["1년 미만"] += 1
            elif years < 3:
                buckets["1~3년"] += 1
            elif years < 5:
                buckets["3~5년"] += 1
            elif years < 10:
                buckets["5~10년"] += 1
            else:
                buckets["10년 이상"] += 1
        except (ValueError, TypeError):
            pass
    conn.close()
    return [{"range": k, "count": v} for k, v in buckets.items()]


def get_division_position_matrix(db_path: str = None) -> Dict:
    """본부 x 직급 히트맵 데이터"""
    conn = _connect(db_path)
    cursor = conn.execute("""
        SELECT division, position, COUNT(*) as count
        FROM employees
        WHERE (is_active=1 OR is_active IS NULL) AND division IS NOT NULL AND position IS NOT NULL
        GROUP BY division, position
    """)
    matrix = defaultdict(lambda: defaultdict(int))
    divisions = set()
    positions = set()

    for row in cursor.fetchall():
        matrix[row["division"]][row["position"]] = row["count"]
        divisions.add(row["division"])
        positions.add(row["position"])
    conn.close()

    sorted_positions = [p for p in POSITION_ORDER if p in positions]
    sorted_divisions = sorted(divisions)

    return {
        "divisions": sorted_divisions,
        "positions": sorted_positions,
        "matrix": {d: {p: matrix[d][p] for p in sorted_positions} for d in sorted_divisions},
    }


def get_overseas_staff(db_path: str = None) -> List[Dict]:
    """해외파견 인력"""
    conn = _connect(db_path)
    try:
        cursor = conn.execute("""
            SELECT name, position, department, overseas_assignment
            FROM employees
            WHERE overseas_assignment IS NOT NULL AND overseas_assignment != ''
                  AND (is_active=1 OR is_active IS NULL)
        """)
        results = [dict(r) for r in cursor.fetchall()]
    except Exception:
        results = []
    conn.close()
    return results
