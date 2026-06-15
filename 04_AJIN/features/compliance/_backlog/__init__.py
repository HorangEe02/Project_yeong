"""Feature D _backlog — Sprint 1 P0 보류 6 모듈.

폐기 대상 3 크롤러 (plan §41 Sprint 2):
  - apqp_crawler: 라이브 외부 소스 0건 (마스터만)
  - oem_quality_crawler: 라이브 외부 소스 0건 (마스터만)
  - us_trade_crawler: 검증 필요, 사내 수요 낮음

기타 보류 3:
  - lms_export: SCORM/xAPI, 사내 LMS 부재로 보류
  - learning_path: D4 학습경로 (Sprint 5 재검토)
  - alarm_aggregator: D1 noisy filter 대안 검토 후 활성화 결정

⚠ 본 모듈을 새로 import 하면 backlog 분류 의도 위반. Sprint 6 결정 시까지 신규 사용 금지.
v4.7 D mv: 물리 이동 완료, 신 sub 경로 import.
"""

from features.compliance.crawlers import (
    apqp_crawler,
    oem_quality_crawler,
    us_trade_crawler,
)
from features.compliance.learning import (
    lms_export,
    learning_path,
)
from features.compliance.alerts import alarm_aggregator

__all__ = [
    "apqp_crawler", "oem_quality_crawler", "us_trade_crawler",
    "lms_export", "learning_path", "alarm_aggregator",
]
