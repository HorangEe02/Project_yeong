"""
AI 시스템 사용 분석 엔진
- audit.db + feedback.db + login_history 종합 분석
- 기능별/부서별/시간대별 사용 패턴 추출
- ROI 정량화 지표 산출
"""

import sqlite3
from datetime import datetime, date, timedelta
from typing import Dict, List
from collections import defaultdict
from pathlib import Path

AUDIT_DB = "data/audit.db"
AUTH_DB = "data/auth.db"
FEEDBACK_DB = "data/feedback.db"

# 엔드포인트 -> 기능 매핑
ENDPOINT_FEATURE_MAP = {
    "/api/employee": "A",
    "/api/search": "A",
    "/api/draft": "B",
    "/api/onboarding": "C",
    "/api/compliance": "D",
    "/api/admin": "E",
    "/api/equipment": "F",
}

FEATURE_NAMES = {
    "A": "인원 검색",
    "B": "문서 작성",
    "C": "AI 도우미",
    "D": "규정 준수",
    "E": "인사 관리",
    "F": "설비/공정",
}

FEATURE_COLORS = {
    "A": "#1976D2",
    "B": "#388E3C",
    "C": "#F57C00",
    "D": "#D32F2F",
    "E": "#7B1FA2",
    "F": "#00796B",
}

# 기능별 예상 수동 소요 시간 (분) -- ROI 산출용
MANUAL_TIME_MINUTES = {
    "A": 3,
    "B": 30,
    "C": 5,
    "D": 15,
    "E": 2,
    "F": 10,
}


def _connect_audit():
    """audit.db 연결"""
    if not Path(AUDIT_DB).exists():
        return None
    try:
        conn = sqlite3.connect(AUDIT_DB)
        return conn
    except Exception:
        return None


def _get_audit_table_name() -> str:
    """audit.db의 실제 테이블명 확인"""
    conn = _connect_audit()
    if not conn:
        return "audit_log"
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        if "api_audit_log" in tables:
            return "api_audit_log"
        if "audit_log" in tables:
            return "audit_log"
        return tables[0] if tables else "audit_log"
    except Exception:
        conn.close()
        return "audit_log"


def get_usage_by_feature(days: int = 30) -> List[Dict]:
    """기능별 사용 횟수"""
    conn = _connect_audit()
    if not conn:
        return [{"feature": f, "name": FEATURE_NAMES[f], "count": 0} for f in "ABCDEF"]

    table = _get_audit_table_name()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        cursor = conn.execute(
            f"SELECT endpoint, COUNT(*) as cnt FROM {table} WHERE timestamp >= ? GROUP BY endpoint",
            (cutoff,)
        )
        feature_counts = defaultdict(int)
        for row in cursor.fetchall():
            endpoint = row[0] or ""
            count = row[1]
            for prefix, feature in ENDPOINT_FEATURE_MAP.items():
                if endpoint.startswith(prefix):
                    feature_counts[feature] += count
                    break
            else:
                # endpoint가 매핑에 없으면 endpoint 자체로 추정
                for f_key in FEATURE_NAMES:
                    if f_key.lower() in endpoint.lower():
                        feature_counts[f_key] += count
                        break
    except Exception:
        feature_counts = {}
    finally:
        conn.close()

    return [
        {"feature": f, "name": FEATURE_NAMES[f], "count": feature_counts.get(f, 0),
         "color": FEATURE_COLORS[f]}
        for f in "ABCDEF"
    ]


def get_usage_by_department(days: int = 30) -> List[Dict]:
    """부서별 사용 횟수"""
    conn = _connect_audit()
    if not conn:
        return []

    table = _get_audit_table_name()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        # audit.db에 department 컬럼이 직접 있음
        cursor = conn.execute(
            f"SELECT department, COUNT(*) as cnt FROM {table} "
            f"WHERE timestamp >= ? AND department != '' "
            f"GROUP BY department ORDER BY cnt DESC",
            (cutoff,)
        )
        results = [{"department": row[0] or "미분류", "count": row[1]} for row in cursor.fetchall()]
    except Exception:
        results = []
    finally:
        conn.close()

    return results


def get_usage_by_hour(days: int = 7) -> List[Dict]:
    """시간대별 사용 분포"""
    conn = _connect_audit()
    hour_counts = defaultdict(int)

    if conn:
        table = _get_audit_table_name()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        try:
            cursor = conn.execute(
                f"SELECT timestamp FROM {table} WHERE timestamp >= ?", (cutoff,)
            )
            for row in cursor.fetchall():
                ts = row[0]
                try:
                    hour = datetime.fromisoformat(ts).hour
                    hour_counts[hour] += 1
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass
        finally:
            conn.close()

    # 로그인 이력도 포함
    if Path(AUTH_DB).exists():
        try:
            auth_conn = sqlite3.connect(AUTH_DB)
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            cursor = auth_conn.execute(
                "SELECT timestamp FROM login_history WHERE timestamp >= ? AND success = 1",
                (cutoff,)
            )
            for row in cursor.fetchall():
                try:
                    hour = datetime.fromisoformat(row[0]).hour
                    hour_counts[hour] += 1
                except (ValueError, TypeError):
                    pass
            auth_conn.close()
        except Exception:
            pass

    return [{"hour": h, "count": hour_counts.get(h, 0)} for h in range(24)]


def get_dept_feature_heatmap(days: int = 30) -> Dict:
    """부서 x 기능 사용 히트맵 데이터"""
    conn = _connect_audit()
    if not conn:
        return {"departments": [], "features": list(FEATURE_NAMES.keys()), "matrix": {}}

    table = _get_audit_table_name()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    matrix = defaultdict(lambda: defaultdict(int))
    departments = set()

    try:
        cursor = conn.execute(
            f"SELECT department, endpoint, COUNT(*) FROM {table} "
            f"WHERE timestamp >= ? AND department != '' "
            f"GROUP BY department, endpoint",
            (cutoff,)
        )
        for row in cursor.fetchall():
            dept = row[0] or "미분류"
            endpoint = row[1] or ""
            count = row[2]
            departments.add(dept)
            for prefix, feature in ENDPOINT_FEATURE_MAP.items():
                if endpoint.startswith(prefix):
                    matrix[dept][feature] += count
                    break
    except Exception:
        pass
    finally:
        conn.close()

    sorted_depts = sorted(departments)
    features = list(FEATURE_NAMES.keys())

    return {
        "departments": sorted_depts,
        "features": features,
        "matrix": {d: {f: matrix[d][f] for f in features} for d in sorted_depts},
    }


def get_daily_active_users(days: int = 30) -> List[Dict]:
    """일별 활성 사용자 수 (DAU)"""
    if not Path(AUTH_DB).exists():
        return []

    try:
        conn = sqlite3.connect(AUTH_DB)
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        cursor = conn.execute(
            """SELECT DATE(timestamp) as login_date, COUNT(DISTINCT employee_id) as dau
               FROM login_history
               WHERE timestamp >= ? AND success = 1
               GROUP BY DATE(timestamp)
               ORDER BY login_date""",
            (cutoff,)
        )
        results = [{"date": row[0], "dau": row[1]} for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception:
        return []


def get_feedback_summary() -> Dict:
    """피드백 요약"""
    if not Path(FEEDBACK_DB).exists():
        return {"total": 0, "positive": 0, "negative": 0, "rate": 0}

    try:
        conn = sqlite3.connect(FEEDBACK_DB)
        total = conn.execute("SELECT COUNT(*) FROM chat_feedback").fetchone()[0]
        positive = conn.execute("SELECT COUNT(*) FROM chat_feedback WHERE is_positive = 1").fetchone()[0]
        conn.close()
        return {
            "total": total,
            "positive": positive,
            "negative": total - positive,
            "rate": round(positive / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        return {"total": 0, "positive": 0, "negative": 0, "rate": 0}


def calculate_roi_estimate(days: int = 30) -> Dict:
    """AI 시스템 ROI 추정"""
    usage = get_usage_by_feature(days=days)

    total_uses = sum(u["count"] for u in usage)
    total_saved_minutes = sum(
        u["count"] * MANUAL_TIME_MINUTES.get(u["feature"], 5) for u in usage
    )

    # 시간 -> 인건비 환산 (연봉 5000만원 기준)
    hourly_cost_krw = 50_000_000 / 12 / 160
    saved_cost_krw = (total_saved_minutes / 60) * hourly_cost_krw

    return {
        "total_uses": total_uses,
        "total_saved_minutes": total_saved_minutes,
        "total_saved_hours": round(total_saved_minutes / 60, 1),
        "saved_cost_krw": round(saved_cost_krw, 0),
        "saved_cost_display": f"{saved_cost_krw / 10000:,.0f}만원" if saved_cost_krw > 0 else "0원",
        "period_days": days,
        "per_feature": {
            u["feature"]: {
                "name": u["name"],
                "count": u["count"],
                "saved_min": u["count"] * MANUAL_TIME_MINUTES.get(u["feature"], 5),
            }
            for u in usage
        },
    }
