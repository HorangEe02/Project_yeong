"""BigQuery audit 분석 클라이언트.

H8 Step D — Cloud Logging Sink 가 BigQuery `ajin-cb.ajin_audit` 데이터셋에
적재한 login 이벤트를 장기 분석 쿼리한다.

테이블:
  ajin_audit.cloud_run_revision_YYYYMMDD  (자동 일별 파티셔닝)
  스키마: timestamp, severity, jsonPayload.{event, user_id, employee_id, success, ip, department, role_level}

본 모듈은 1~5분 sink 지연을 감안한 "콜드 패스" 전용. SecurityTab 의 실시간
화면(30s 폴링)은 H7 Firestore audit_logs 로 처리.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT = "ajin-cb"
DATASET = "ajin_audit"


def _client():
    """BigQuery 클라이언트 lazy init."""
    from google.cloud import bigquery  # type: ignore
    return bigquery.Client(project=PROJECT)


def is_available() -> bool:
    try:
        _client()
        return True
    except Exception:
        return False


def fetch_hour_distribution(days: int = 30) -> list[dict]:
    """24-bin 시간대 분포 (장기 데이터)."""
    query = f"""
    SELECT
      EXTRACT(HOUR FROM TIMESTAMP(jsonPayload.timestamp)) AS hour,
      COUNT(*) AS count,
      COUNTIF(jsonPayload.success) AS success_count
    FROM `{PROJECT}.{DATASET}.cloud_run_revision_*`
    WHERE jsonPayload.event = 'login'
      AND DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
    GROUP BY hour
    ORDER BY hour
    """
    from google.cloud import bigquery  # type: ignore
    try:
        c = _client()
        job = c.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)]
            ),
        )
        rows = []
        for r in job.result():
            rows.append({"hour": r.hour, "count": r.count, "success_count": r.success_count})
        # 24-bin 보장 (빈 hour 는 0)
        existing = {r["hour"]: r for r in rows}
        return [
            existing.get(h, {"hour": h, "count": 0, "success_count": 0})
            for h in range(24)
        ]
    except Exception as e:
        logger.warning("[bq_audit] fetch_hour_distribution 실패: %s", e)
        return [{"hour": h, "count": 0, "success_count": 0} for h in range(24)]


def fetch_department_dau(days: int = 30) -> list[dict]:
    """부서별 일일 활성 사용자 (DAU)."""
    query = f"""
    SELECT
      jsonPayload.department AS department,
      DATE(timestamp) AS date,
      COUNT(DISTINCT jsonPayload.user_id) AS dau,
      COUNT(*) AS total_logins,
      COUNTIF(NOT jsonPayload.success) AS failed
    FROM `{PROJECT}.{DATASET}.cloud_run_revision_*`
    WHERE jsonPayload.event = 'login'
      AND DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
      AND jsonPayload.department IS NOT NULL
    GROUP BY department, date
    ORDER BY date DESC, dau DESC
    """
    from google.cloud import bigquery  # type: ignore
    try:
        c = _client()
        job = c.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)]
            ),
        )
        return [
            {
                "department": r.department or "",
                "date": r.date.isoformat() if r.date else "",
                "dau": r.dau,
                "total_logins": r.total_logins,
                "failed": r.failed,
            }
            for r in job.result()
        ]
    except Exception as e:
        logger.warning("[bq_audit] fetch_department_dau 실패: %s", e)
        return []


def fetch_summary(days: int = 30) -> dict:
    """전체 요약: 총 로그인 / 고유 사용자 / 실패율."""
    query = f"""
    SELECT
      COUNT(*) AS total,
      COUNTIF(jsonPayload.success) AS success,
      COUNT(DISTINCT jsonPayload.user_id) AS unique_users
    FROM `{PROJECT}.{DATASET}.cloud_run_revision_*`
    WHERE jsonPayload.event = 'login'
      AND DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
    """
    from google.cloud import bigquery  # type: ignore
    try:
        c = _client()
        job = c.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)]
            ),
        )
        for r in job.result():
            total = r.total or 0
            success = r.success or 0
            return {
                "days": days,
                "total": total,
                "success": success,
                "failed": total - success,
                "success_rate": (success / total) if total else 0.0,
                "unique_users": r.unique_users or 0,
            }
        return {"days": days, "total": 0, "success": 0, "failed": 0, "success_rate": 0.0, "unique_users": 0}
    except Exception as e:
        logger.warning("[bq_audit] fetch_summary 실패: %s", e)
        return {"days": days, "total": 0, "success": 0, "failed": 0, "success_rate": 0.0, "unique_users": 0, "error": str(e)}


def fetch_archived_logins(date: str, limit: int = 500) -> list[dict]:
    """특정 일자(`YYYY-MM-DD`)의 archived 로그인 이력 (90일 초과 영역).

    v4.9.2 — SecurityTab 달력 90일 초과 일자 클릭 시 호출.
    스키마: timestamp, employee_id, username, success, ip_address, department, role_name.

    GCP 인증 미설정 시 graceful — 빈 리스트 반환.
    """
    query = f"""
    SELECT
      jsonPayload.timestamp AS timestamp,
      jsonPayload.employee_id AS employee_id,
      jsonPayload.username AS username,
      jsonPayload.success AS success,
      jsonPayload.ip AS ip_address,
      jsonPayload.department AS department,
      CAST(jsonPayload.role_level AS STRING) AS role_name
    FROM `{PROJECT}.{DATASET}.cloud_run_revision_*`
    WHERE jsonPayload.event = 'login'
      AND DATE(timestamp) = DATE(@d)
    ORDER BY timestamp DESC
    LIMIT @lim
    """
    from google.cloud import bigquery  # type: ignore
    try:
        c = _client()
        job = c.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("d", "STRING", date),
                    bigquery.ScalarQueryParameter("lim", "INT64", limit),
                ]
            ),
        )
        return [
            {
                "timestamp": str(r.timestamp or ""),
                "employee_id": r.employee_id or "",
                "username": r.username or "",
                "action": "login",
                "success": bool(r.success) if r.success is not None else True,
                "ip_address": r.ip_address or "",
                "department": r.department or "",
                "role_name": r.role_name or "",
                "flag": None,
            }
            for r in job.result()
        ]
    except Exception as e:
        logger.warning("[bq_audit] fetch_archived_logins(%s) 실패: %s", date, e)
        return []
