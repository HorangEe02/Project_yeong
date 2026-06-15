"""v4.8 Feature F 트랙 A — PLC/SCADA 실시간 메시지 시뮬레이터.

Redis Stream `plc:lane:<line_id>` 에 측정값을 일정 주기로 XADD.

사용 예시:
    python scripts/simulate_plc_stream.py --duration 30 --rate 1 --lanes 3
    python scripts/simulate_plc_stream.py --duration 60 --inject-violation R1

inject-violation 사용 시 Nelson Rule 위반을 의도적으로 유도하는 값 범주를
한 라인에 한정해 발행한다 (e.g. R1 → 평균+5σ 큰 값을 1개 끼움).

Redis 미가용 환경에서는 ConnectionError 로 종료 — dry-run 옵션은 미제공
(시뮬은 인프라가 떠 있다는 전제이므로 실패를 명시).
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("plc_simulator")

# 5공정 baseline (process: (mean, std, metric))
_PROCESS_BASELINES = {
    "cch_plate_thickness": (3.20, 0.04, "cycle_count"),
    "obc_case_flatness": (0.10, 0.02, "pressure"),
    "ewp_housing_bore": (50.00, 0.05, "temperature"),
    "bumper_nugget_diameter": (5.50, 0.10, "cycle_count"),
    "seatrail_hole_position": (0.15, 0.03, "pressure"),
}

_RUNNING = True


def _signal_handler(signum, frame) -> None:  # noqa: ARG001
    global _RUNNING
    _RUNNING = False
    logger.info("SIGTERM/SIGINT 수신 — graceful shutdown")


def _build_payload(
    process: str,
    line_id: str,
    inject_violation: Optional[str],
    sample_idx: int,
) -> dict:
    mean, std, metric = _PROCESS_BASELINES[process]

    # 정상 분포
    value = random.gauss(mean, std)

    # 위반 주입 — Rule 1 (±3σ 초과) 만 단순 주입.
    # 다른 룰(2/3 등)은 연속 패턴이 필요하므로 본 시뮬은 R1 한정.
    if inject_violation == "R1" and sample_idx % 30 == 15:
        # 평균에서 +5σ 떨어뜨려 UCL(3σ) 명백히 위반.
        value = mean + 5 * std
        logger.info(f"  → inject R1 violation @ sample {sample_idx}: value={value:.4f}")

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "line_id": line_id,
        "process": process,
        "metric": metric,
        "value": f"{value:.6f}",
        "lot_id": f"LOT-{line_id}-{datetime.now().strftime('%Y%m%d')}",
        "source": "simulator",
    }


def run(
    duration: int = 60,
    rate: float = 1.0,
    lanes: int = 3,
    inject_violation: Optional[str] = None,
    stream_prefix: Optional[str] = None,
) -> dict:
    """시뮬레이션 실행. dict 통계 반환."""
    try:
        import redis
    except ImportError as e:
        raise RuntimeError(f"redis 패키지가 필요합니다: {e}") from e

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    prefix = stream_prefix or os.environ.get("PLC_REDIS_STREAM_KEY_PREFIX", "plc:lane:")

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        client.ping()
    except Exception as e:
        raise ConnectionError(f"Redis 연결 실패 ({redis_url}): {e}") from e

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    processes = list(_PROCESS_BASELINES.keys())
    interval = 1.0 / rate if rate > 0 else 1.0
    deadline = time.time() + duration

    sent = 0
    sample_idx = 0

    logger.info(
        f"PLC 시뮬레이터 시작 — duration={duration}s rate={rate}Hz lanes={lanes} "
        f"inject={inject_violation or 'none'} prefix='{prefix}'"
    )

    while _RUNNING and time.time() < deadline:
        for lane_no in range(1, lanes + 1):
            line_id = f"L{lane_no:02d}"
            process = processes[lane_no % len(processes)]
            stream_key = f"{prefix}{line_id}"
            payload = _build_payload(process, line_id, inject_violation, sample_idx)
            try:
                client.xadd(stream_key, payload, maxlen=10_000, approximate=True)
                sent += 1
            except Exception as e:
                logger.warning(f"xadd 실패 ({stream_key}): {e}")
        sample_idx += 1
        time.sleep(interval)

    logger.info(f"시뮬 종료 — sent={sent} messages across {lanes} lanes")
    return {"sent": sent, "lanes": lanes, "duration": duration}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PLC/SCADA Redis Stream 시뮬레이터")
    p.add_argument("--duration", type=int, default=60, help="실행 시간 (초)")
    p.add_argument("--rate", type=float, default=1.0, help="라인 당 초당 메시지 (Hz)")
    p.add_argument("--lanes", type=int, default=3, help="동시 라인 수")
    p.add_argument(
        "--inject-violation",
        type=str,
        default=None,
        choices=[None, "R1"],
        help="Nelson Rule 번호 위반 주입 (R1 만 지원)",
    )
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    try:
        run(
            duration=args.duration,
            rate=args.rate,
            lanes=args.lanes,
            inject_violation=args.inject_violation,
        )
    except (ConnectionError, RuntimeError) as e:
        logger.error(str(e))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
