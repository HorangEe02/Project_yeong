"""v4.8 Feature F 트랙 A — PLC Redis Stream consumer + Nelson 분석 + live_alarms 저장.

흐름:
    XREADGROUP plc:lane:* (consumer group `equipment_spc_consumers`)
    → 슬라이딩 윈도우 (process 별 last 100 samples)
    → 윈도우 도달 시 spc_realtime.analyze_nelson_rules() 호출
    → 위반 발견 시:
       1) spc_violations_db.insert_violation()
       2) violation_to_alarm() 변환
       3) live_events.insert_alarm(alarm)

본 모듈은 standalone worker process 로 가동되며, FastAPI 와 분리.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Iterable

from features.equipment.plc_adapters import MeasurementContractError, normalize_measurement_event

logger = logging.getLogger(__name__)

# 슬라이딩 윈도우 크기 — Nelson 8 Rules 의 R7(15연속 ±1σ 내) 적용에 충분.
WINDOW_SIZE = 100

# 동일 process+rule 위반 중복 발화 억제 윈도우(초).
_DEDUP_TTL = 60.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# severity 변환 매트릭스: spc_realtime → live alarm.
# 액션 3.A.6 스펙: critical→CRITICAL, warning→HIGH, info→MEDIUM.
# (알람 등급은 4단계 — CRITICAL/HIGH/MEDIUM/LOW.)
_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "warning": "HIGH",
    "info": "MEDIUM",
}


def violation_to_alarm(
    violation: Any,
    process: str,
    line_id: str,
    lot_id: str,
    violation_id: str,
    source: str = "plc_ingest",
) -> dict[str, Any]:
    """spc_realtime.NelsonViolation → live alarm 페이로드.

    Postgres `live_alarms` 테이블과 프론트 알람 피드가 소비하는 표준 스키마.
    """
    return {
        "id": violation_id,
        "type": "spc_violation",
        "severity": _SEVERITY_MAP.get(getattr(violation, "severity", "info"), "INFO"),
        "rule_number": int(getattr(violation, "rule_number", 0)),
        "rule_name": getattr(violation, "rule_name", ""),
        "description": getattr(violation, "description", ""),
        "process": process,
        "line_id": line_id,
        "lot_id": lot_id,
        "violating_count": len(getattr(violation, "violating_indices", []) or []),
        "recommended_action": getattr(violation, "recommended_action", ""),
        "detected_at": _now_iso(),
        "source": source,
    }


def _ensure_group(client: Any, stream_key: str, group: str) -> None:
    """Consumer group 생성 — 이미 존재하면 무시."""
    try:
        client.xgroup_create(stream_key, group, id="$", mkstream=True)
        logger.info(f"consumer group 생성: {stream_key} / {group}")
    except Exception as e:
        # BUSYGROUP — 이미 존재
        if "BUSYGROUP" in str(e):
            return
        logger.warning(f"xgroup_create 실패 ({stream_key}): {e}")


def _discover_streams(client: Any, prefix: str) -> list[str]:
    """KEYS prefix* — small dev 환경에서만 안전. 운영에서는 명시적 라인 목록 권장."""
    try:
        return [str(k) for k in client.keys(f"{prefix}*")]
    except Exception as e:
        logger.warning(f"stream 검색 실패: {e}")
        return []


def _process_message(
    fields: dict[str, str],
    windows: dict[str, deque],
    dedup: dict[str, float],
    on_violation: Any,
) -> int:
    """단일 메시지 처리. 위반 발견 수 반환."""
    try:
        event = normalize_measurement_event(fields)
    except MeasurementContractError as exc:
        logger.warning("measurement contract 위반: %s", exc)
        return 0

    process = event.process
    value = event.value
    line_id = event.line_id
    lot_id = event.lot_id

    win = windows[process]
    win.append(value)

    if len(win) < 10:
        return 0  # Nelson 최소 샘플 미만

    # Nelson 분석 — 매 메시지마다 호출 (윈도우가 차야만 유효)
    try:
        from features.equipment.spc_realtime import analyze_nelson_rules
    except Exception as e:
        logger.error(f"spc_realtime import 실패: {e}")
        return 0

    result = analyze_nelson_rules(list(win), process_name=process)
    if not result.violations:
        return 0

    violations_emitted = 0
    now = time.time()
    for v in result.violations:
        dedup_key = f"{process}:{v.rule_number}:{v.severity}"
        last_seen = dedup.get(dedup_key, 0.0)
        if now - last_seen < _DEDUP_TTL:
            continue
        dedup[dedup_key] = now

        violation_id = f"plc_{process}_R{v.rule_number}_{uuid.uuid4().hex[:8]}"
        try:
            _dispatch_violation(
                on_violation,
                v,
                process,
                line_id,
                lot_id,
                violation_id,
                source_system=event.source_system,
            )
            violations_emitted += 1
        except Exception as e:
            logger.exception(f"on_violation 콜백 실패: {e}")

    return violations_emitted


def _dispatch_violation(
    callback: Any,
    violation: Any,
    process: str,
    line_id: str,
    lot_id: str,
    violation_id: str,
    *,
    source_system: str,
) -> None:
    """Call a violation callback with source lineage when supported.

    Args:
        callback: Violation callback.
        violation: Nelson violation object.
        process: SPC process id.
        line_id: Line id.
        lot_id: Lot id.
        violation_id: Stable generated violation id.
        source_system: Canonical source system from the measurement contract.
    """

    try:
        import inspect

        params = inspect.signature(callback).parameters
        accepts_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
        if "source_system" in params or accepts_kw:
            callback(
                violation,
                process,
                line_id,
                lot_id,
                violation_id,
                source_system=source_system,
            )
            return
    except (TypeError, ValueError):
        pass
    callback(violation, process, line_id, lot_id, violation_id)


def _persist_and_push(
    violation: Any,
    process: str,
    line_id: str,
    lot_id: str,
    violation_id: str,
    source_system: str = "plc_ingest",
) -> None:
    """위반 → SQLite INSERT + live_alarms insert."""
    data_class = "synthetic" if source_system == "plc_simulator" else "real"
    try:
        from features.equipment.spc_violations_db import insert_violation

        insert_violation(
            violation_id=violation_id,
            process=process,
            lot_id=lot_id or "unknown",
            rule_number=int(violation.rule_number),
            rule_name=violation.rule_name,
            violating_count=len(violation.violating_indices or []),
            severity=violation.severity,
            recommended_action=violation.recommended_action,
            data_class=data_class,
            source_system=source_system,
            source_label=source_system,
        )
    except Exception as e:
        logger.warning(f"spc_violations_db.insert 실패: {e}")

    alarm = violation_to_alarm(
        violation,
        process,
        line_id,
        lot_id,
        violation_id,
        source=source_system,
    )
    try:
        from backend.services.live_events import insert_alarm

        insert_alarm(
            alarm,
            domain="equipment",
            data_class=data_class,
            source_system=source_system,
            source_label=source_system,
        )
    except Exception as e:
        logger.warning(f"live_events.insert_alarm 실패: {e}")


def consume(
    client: Any | None = None,
    stream_prefix: str | None = None,
    group: str | None = None,
    consumer_name: str | None = None,
    block_ms: int = 5000,
    max_iterations: int | None = None,
    on_violation: Any | None = None,
) -> dict[str, int]:
    """Long-running consumer loop.

    Args:
        client: redis.Redis 인스턴스. None 이면 REDIS_URL 로 생성.
        stream_prefix: e.g. "plc:lane:" (env: PLC_REDIS_STREAM_KEY_PREFIX)
        group: consumer group 이름 (env: PLC_CONSUMER_GROUP)
        consumer_name: 워커 ID (default: hostname-pid)
        block_ms: XREADGROUP BLOCK 시간
        max_iterations: None 이면 무한 루프 — 테스트에서만 유한 값.
        on_violation: 위반 발견 시 콜백.
            signature (violation, process, line_id, lot_id, violation_id) -> None
            None 이면 _persist_and_push 기본 동작.

    Returns:
        dict 통계 (테스트 친화) — {messages, violations}
    """
    if client is None:
        try:
            import redis  # type: ignore
        except ImportError as e:
            raise RuntimeError(f"redis 패키지 필요: {e}") from e
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        client = redis.Redis.from_url(redis_url, decode_responses=True)

    prefix = stream_prefix or os.environ.get("PLC_REDIS_STREAM_KEY_PREFIX", "plc:lane:")
    group_name = group or os.environ.get("PLC_CONSUMER_GROUP", "equipment_spc_consumers")
    consumer = consumer_name or f"worker-{os.getpid()}"
    cb = on_violation or _persist_and_push

    windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    dedup: dict[str, float] = {}
    stats = {"messages": 0, "violations": 0}

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1

        # Stream 목록 + group 보장
        streams = _discover_streams(client, prefix)
        if not streams:
            logger.debug(f"활성 stream 없음 (prefix={prefix}) — 대기")
            time.sleep(block_ms / 1000.0)
            continue

        for s in streams:
            _ensure_group(client, s, group_name)

        # 모든 라인에서 한 번에 read
        try:
            stream_map = {s: ">" for s in streams}
            resp = client.xreadgroup(
                group_name, consumer, stream_map, count=50, block=block_ms
            )
        except Exception as e:
            logger.warning(f"xreadgroup 실패: {e}")
            time.sleep(1.0)
            continue

        if not resp:
            continue

        for stream_key, entries in resp:
            for msg_id, fields in entries:
                stats["messages"] += 1
                try:
                    v_count = _process_message(fields, windows, dedup, cb)
                    stats["violations"] += v_count
                except Exception as e:
                    logger.exception(f"메시지 처리 실패 ({stream_key}/{msg_id}): {e}")
                # ACK — at-least-once 보장
                try:
                    client.xack(stream_key, group_name, msg_id)
                except Exception as e:
                    logger.warning(f"xack 실패: {e}")

    return stats


def process_batch(
    messages: Iterable[dict[str, str]],
    on_violation: Any | None = None,
) -> dict[str, int]:
    """테스트/배치 모드 — Redis 없이 메시지 리스트를 직접 주입.

    Args:
        messages: dict iterable. 각 dict 은 simulate_plc_stream payload 와 동일 형식.
        on_violation: 위반 콜백 (default _persist_and_push).
    """
    windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    dedup: dict[str, float] = {}
    cb = on_violation or _persist_and_push
    stats = {"messages": 0, "violations": 0}

    for fields in messages:
        stats["messages"] += 1
        v_count = _process_message(fields, windows, dedup, cb)
        stats["violations"] += v_count

    return stats
