"""Feature D D5 Supply — 협력사 관리 5 모듈.

Sprint 4 — N2 자가진단 포털 + mail_guard (Feature B) 로 외부 발송 봉인.
v4.7 D mv: 물리 이동 완료, 신 sub 경로 import.
"""

from features.compliance.supply import (
    supplier_compliance,
    supplier_graph,
    supplier_discovery,
    supplier_recommender,
    industry_trend,
)

__all__ = [
    "supplier_compliance", "supplier_graph",
    "supplier_discovery", "supplier_recommender",
    "industry_trend",
]
