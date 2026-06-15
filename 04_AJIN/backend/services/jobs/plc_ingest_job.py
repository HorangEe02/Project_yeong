"""v4.8 Feature F 트랙 A — PLC ingest worker entrypoint.

`features.equipment.plc_ingest.consume()` 의 standalone 래퍼.

기동:
    python -m backend.services.jobs.plc_ingest_job

본 워커는 Celery task 가 아닌 long-running process 로 배포되며,
Cloud Run sidecar 또는 별도 GKE pod 에서 가동된다.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_SHOULD_STOP = False


def _handle_signal(signum, frame) -> None:  # noqa: ARG001
    global _SHOULD_STOP
    _SHOULD_STOP = True
    logger.info("SIGTERM/SIGINT — graceful shutdown 요청 수신")


def start_plc_ingest_worker(
    stream_prefix: Optional[str] = None,
    group: Optional[str] = None,
    block_ms: int = 5000,
) -> dict:
    """워커 메인 루프. SIGTERM 까지 영구 실행.

    Returns: 종료 시점 통계 dict.
    """
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    from features.equipment import plc_ingest

    # consume() 는 자체 루프를 돌리지만 max_iterations=None 이라 SIGTERM 으로
    # 빠져나오지 않는다 — 따라서 짧은 batch 로 반복 호출하면서 _SHOULD_STOP 체크.
    aggregate = {"messages": 0, "violations": 0}
    logger.info("PLC ingest worker 기동")
    while not _SHOULD_STOP:
        try:
            stats = plc_ingest.consume(
                stream_prefix=stream_prefix,
                group=group,
                block_ms=block_ms,
                max_iterations=1,  # 1 iteration = 1 XREADGROUP cycle
            )
            aggregate["messages"] += stats.get("messages", 0)
            aggregate["violations"] += stats.get("violations", 0)
        except Exception as e:
            logger.exception(f"consume 루프 예외 (재시도): {e}")

    logger.info(f"PLC ingest worker 종료 — total={aggregate}")
    return aggregate


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    try:
        start_plc_ingest_worker()
        return 0
    except Exception as e:
        logger.exception(f"워커 비정상 종료: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
