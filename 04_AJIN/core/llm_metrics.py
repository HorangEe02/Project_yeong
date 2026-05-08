"""LLM 호출 메트릭 기록기 — RotatingFileHandler + 인메모리 카운터.

JSON Lines 포맷으로 logs/llm_metrics.log 에 기록 (10MB × 5 backups).
인메모리 카운터는 (provider, mode) 키로 success/failure 누적.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


_METRICS_LOGGER_NAME = "ajin.llm_metrics"


def _build_logger(log_path: str, level: str) -> logging.Logger:
    logger = logging.getLogger(_METRICS_LOGGER_NAME)
    # 이미 초기화된 경우 핸들러 중복 등록 방지
    if logger.handlers:
        return logger

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger


class MetricsRecorder:
    """LLM 호출 메트릭 — 디스크 기록 + 인메모리 집계."""

    def __init__(
        self,
        log_path: str | None = None,
        enabled: bool | None = None,
        log_level: str | None = None,
    ) -> None:
        self.log_path = log_path or os.getenv("LLM_METRICS_LOG_PATH", "logs/llm_metrics.log")
        env_enabled = os.getenv("LLM_METRICS_ENABLED", "true").lower() == "true"
        self.enabled = env_enabled if enabled is None else enabled
        self.log_level = log_level or os.getenv("LLM_METRICS_LOG_LEVEL", "INFO")

        self._logger: logging.Logger | None = None
        if self.enabled:
            self._logger = _build_logger(self.log_path, self.log_level)

        self.counters: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {"success": 0, "failure": 0}
        )
        self._latencies: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _emit(self, payload: dict[str, Any]) -> None:
        if not self.enabled or self._logger is None:
            return
        try:
            self._logger.info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            # 메트릭 실패가 라우팅을 깨면 안 됨
            pass

    def record_success(
        self,
        provider: str,
        mode: str,
        ttft_ms: float | None = None,
        latency_ms: float | None = None,
    ) -> None:
        self.counters[(provider, mode)]["success"] += 1
        if latency_ms is not None:
            self._latencies[(provider, mode)].append(latency_ms)
        self._emit({
            "ts": time.time(),
            "provider": provider,
            "mode": mode,
            "event": "success",
            "ttft_ms": round(ttft_ms, 2) if ttft_ms is not None else None,
            "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        })

    def record_failure(self, provider: str, mode: str, error: str) -> None:
        self.counters[(provider, mode)]["failure"] += 1
        self._emit({
            "ts": time.time(),
            "provider": provider,
            "mode": mode,
            "event": "failure",
            "error": error[:500],
        })

    def snapshot(self) -> dict[str, Any]:
        counters_dict = {
            f"{p}:{m}": dict(v) for (p, m), v in self.counters.items()
        }
        latency_summary: dict[str, dict[str, float]] = {}
        for (p, m), latencies in self._latencies.items():
            if not latencies:
                continue
            latency_summary[f"{p}:{m}"] = {
                "count": len(latencies),
                "avg_ms": round(sum(latencies) / len(latencies), 2),
                "max_ms": round(max(latencies), 2),
            }
        return {
            "counters": counters_dict,
            "latency": latency_summary,
            "log_path": self.log_path,
            "enabled": self.enabled,
        }
