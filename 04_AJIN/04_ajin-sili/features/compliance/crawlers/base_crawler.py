"""BaseCrawler — Phase 1 진짜 크롤러 공통 골격.

기존 9개 크롤러 dataclass 결과 형태(`crawled_at`, `source`, `total_count`,
`data`)는 그대로 유지하되, 본 클래스를 상속받으면:
  - 일자별 스냅샷 디렉터리 (`data/crawled/<name>/<YYYYMMDD>.json`) 자동 관리
  - 직전 스냅샷 폴백 (fetch 실패 시 errors 반환하고 빈 화면 방지)
  - compliance.db 자동 적재 (이미 정의된 save_crawl_result 활용)
  - source_type ("live" | "curated") 일관 노출 → UI 배지용
가 갖춰진다.

기존 단일 파일 (`data/crawled/<name>.json`) 도 하위 호환을 위해 그대로
덮어쓴다 (UI 의 기존 read 경로 깨지지 않도록).
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

SourceType = Literal["live", "curated"]


class BaseCrawler(ABC):
    """진짜 HTTP 크롤러의 추상 베이스.

    서브클래스는 최소 `crawler_name`, `display_name`, `doc_type`, `legacy_filename`
    클래스 변수를 정의하고 `_fetch_live()` 만 구현하면 된다.

    `_fetch_live()` 가 None 또는 빈 리스트를 돌려주거나 예외를 던지면 자동으로
    `_curated_fallback()` 으로 떨어진다.
    """

    crawler_name: str = ""
    display_name: str = ""
    doc_type: str = ""
    legacy_filename: str = ""           # 기존 단일 파일 (예: "domestic_laws.json")
    id_key: str = "id"                  # save_crawl_result 의 reg_id 추출 키
    name_key: str = "name"
    status_key: str | None = None       # 준수 상태 키 (없으면 None)
    source_label: str = ""              # 예: "law.go.kr OpenAPI"

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.data_dir = data_dir
        self.snapshot_dir = data_dir / self.crawler_name
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.legacy_path = data_dir / self.legacy_filename if self.legacy_filename else None
        # F9/F12 — 마지막 HTTP 호출 메타 (status/etag/last_modified). crawl() 결과에 포함.
        self._last_http_meta: dict | None = None

    # F9 — ETag 캐시 통합 fetch helper. 서브클래스 _fetch_live 가 직접 사용.
    def _cached_fetch_json(self, url: str, **kwargs):
        """fetch_json + http_cache 자동 통합. 304 시 None 반환 (caller 가 캐시 사용)."""
        return self._cached_fetch(url, parser="json", **kwargs)

    # F11 — HTML 페이지 페치 + BeautifulSoup 파싱 헬퍼.
    # ECHA candidate list / CBAM / KEITI 등 server-rendered HTML 사이트용.
    # SPA / JS-rendered 사이트는 v5+ playwright 도입 후 분리.
    def _cached_fetch_html(self, url: str, parser: str = "lxml", **kwargs):
        """fetch HTML + BeautifulSoup 트리 반환. 304 시 None."""
        return self._cached_fetch(url, parser="html", html_parser=parser, **kwargs)

    def _cached_fetch(self, url: str, parser: str, html_parser: str = "lxml", **kwargs):
        """공통 conditional GET + 파싱. parser ∈ {"json", "html", "raw"}."""
        from features.compliance.infra._http import fetch
        from backend.services.http_cache import get_cache, upsert_cache

        cached = get_cache(url) or {}
        headers = dict(kwargs.pop("headers", {}))
        if cached.get("etag"):
            headers.setdefault("If-None-Match", cached["etag"])
        if cached.get("last_modified"):
            headers.setdefault("If-Modified-Since", cached["last_modified"])

        resp = fetch(url, headers=headers, **kwargs)
        new_etag = resp.headers.get("ETag", "") or cached.get("etag", "")
        new_lm = resp.headers.get("Last-Modified", "") or cached.get("last_modified", "")
        try:
            upsert_cache(url, new_etag, new_lm, resp.status_code)
        except Exception:
            pass

        self._last_http_meta = {
            "status": resp.status_code,
            "etag": new_etag,
            "last_modified": new_lm,
        }
        if resp.status_code == 304:
            return None

        if parser == "json":
            return resp.json()
        if parser == "html":
            from bs4 import BeautifulSoup
            return BeautifulSoup(resp.text, html_parser)
        return resp

    # ── 서브클래스 오버라이드 ──
    @abstractmethod
    def _fetch_live(self) -> list[dict]:
        """외부 API/페이지에서 정규화된 dict 리스트를 반환. 실패 시 예외 throw."""

    @abstractmethod
    def _curated_fallback(self) -> list[dict]:
        """크레덴셜 미설정·외부 실패 시 사용할 큐레이트 데이터."""

    def _credentials_ready(self) -> bool:
        """크레덴셜 사전 점검 — `_fetch_live` 호출 전에 짧게 컷."""
        return True

    # ── 공통 파이프라인 ──
    def crawl(self) -> dict:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors: list[str] = []
        source_type: SourceType = "curated"
        items: list[dict] = []

        if self._credentials_ready():
            try:
                items = list(self._fetch_live() or [])
                if items:
                    source_type = "live"
                else:
                    errors.append("live fetch returned 0 items — falling back to curated")
            except Exception as e:
                logger.warning("[%s] live fetch failed: %s", self.crawler_name, e)
                errors.append(f"live fetch failed: {type(e).__name__}: {e}")
        else:
            errors.append("credentials not configured — using curated fallback")

        if not items:
            try:
                items = list(self._curated_fallback() or [])
            except Exception as e:
                logger.exception("[%s] curated fallback failed: %s", self.crawler_name, e)
                errors.append(f"curated fallback failed: {e}")
                items = []

        result = {
            "crawler_name": self.crawler_name,
            "display_name": self.display_name,
            "crawled_at": now,
            "source": self.source_label or self.display_name,
            "source_type": source_type,
            "total_count": len(items),
            "errors": errors,
            "data": items,
            # F9/F12 — 마지막 HTTP 응답 메타 (audit 적재용).
            "http_meta": self._last_http_meta or {},
        }

        # MVP Stage 2~6 — diff 감지 → 분류 → save_changes → Slack 라우팅
        # 반드시 _persist_snapshot 보다 먼저 — 이전 스냅샷을 today 가 덮어쓰지 않도록.
        try:
            change_summary = self._run_diff(items)
            if change_summary:
                result["change_summary"] = change_summary
        except Exception as e:
            logger.exception("[%s] _run_diff failed: %s", self.crawler_name, e)
            result["errors"].append(f"diff pipeline failed: {type(e).__name__}: {e}")

        # 영속화 (실패해도 결과는 그대로 반환 — UI 가 빈 화면 안 띄우도록)
        try:
            self._persist_snapshot(result)
        except Exception as e:
            logger.exception("[%s] snapshot persist failed: %s", self.crawler_name, e)
            result["errors"].append(f"snapshot persist failed: {e}")

        try:
            self._save_to_compliance_db(items, now, errors)
        except Exception as e:
            logger.exception("[%s] compliance.db persist failed: %s", self.crawler_name, e)
            result["errors"].append(f"compliance.db persist failed: {e}")

        return result

    # ── MVP Stage 2~6 — 변경 감지 + 분류 + 적재 + 알림 ──
    def _run_diff(self, new_items: list[dict]) -> dict | None:
        """이전 스냅샷 ↔ 신규 items 비교 → 분류 → DB 저장 → Slack 라우팅.

        Returns:
            요약 dict {detected, substantive, filtered, slack: {sent, skipped, failed}}
            또는 None — 첫 실행 (이전 스냅샷 부재) 시 diff 스킵.
        """
        # 첫 실행 가드 — 이전 스냅샷 없으면 모든 항목이 'added' 로 잡혀 알림 폭증.
        # 단, 같은 날 두 번째 이상 실행은 정상 진행 (오늘 스냅샷이 이미 있음).
        snaps = sorted(self.snapshot_dir.glob("*.json")) if self.snapshot_dir.exists() else []
        if not snaps:
            logger.info("[%s] 첫 실행 — diff 스킵", self.crawler_name)
            return None

        # 이전 스냅샷 로드 — 가장 최근 파일
        old_items = self._load_previous_snapshot()
        if not old_items:
            logger.info("[%s] 이전 스냅샷 비어있음 — diff 스킵", self.crawler_name)
            return None

        from features.compliance.alerts.change_detector import detect_changes, save_changes
        from features.compliance.alerts.change_classifier import classify_batch

        raw_changes = detect_changes(
            regulation_type=self.crawler_name,
            old_data=old_items,
            new_data=new_items,
            id_field=self.id_key,
        )
        if not raw_changes:
            return {"detected": 0, "substantive": 0, "filtered": 0,
                    "slack": {"sent": 0, "skipped": 0, "failed": 0},
                    "sms": {"sent": 0, "skipped": 0, "failed": 0}}

        classified = classify_batch(raw_changes)
        substantive = [c for c in classified if c.get("is_substantive")]
        filtered = [c for c in classified if not c.get("is_substantive")]

        # 모든 변경(노이즈 포함)을 DB 에 적재 — filtered 는 status='filtered'
        new_ids = save_changes(classified)

        # Slack + SMS 직접 발송은 P2 이후 기본 봉인한다.
        # 표준 경로는 save_changes() → notifications.db outbox → dispatcher 이다.
        substantive_ids = [
            nid for nid, c in zip(new_ids, classified) if c.get("is_substantive")
        ]
        notify_counts = {
            "slack": {"sent": 0, "skipped": len(substantive), "failed": 0},
            "sms": {"sent": 0, "skipped": len(substantive), "failed": 0},
        }
        if os.environ.get("FEATURE_D_LEGACY_DIRECT_NOTIFY", "").strip().lower() in (
            "1", "true", "yes", "on",
        ):
            from features.compliance.alerts.notify import route_batch as notify_route_batch

            notify_counts = notify_route_batch(substantive, substantive_ids)

        summary = {
            "detected": len(classified),
            "substantive": len(substantive),
            "filtered": len(filtered),
            **notify_counts,
        }
        logger.info("[%s] diff %s", self.crawler_name, summary)
        return summary

    # ── 영속화 ──
    def _persist_snapshot(self, result: dict) -> None:
        """일자별 스냅샷 + 레거시 단일 파일 동시 갱신."""
        # 1) 신규 일자별 스냅샷
        date_tag = datetime.now().strftime("%Y%m%d")
        snap_path = self.snapshot_dir / f"{date_tag}.json"
        snap_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 2) 하위 호환용 레거시 파일 — 기존 UI 코드 깨지지 않도록 갱신
        if self.legacy_path:
            self.legacy_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _save_to_compliance_db(
        self, items: list[dict], crawled_at: str, errors: list[str]
    ) -> None:
        if not items:
            return
        try:
            from features.compliance.infra.compliance_db import save_crawl_result
        except Exception:
            return
        save_crawl_result(
            crawler_name=self.crawler_name,
            display_name=self.display_name,
            json_filename=self.legacy_filename or f"{self.crawler_name}.json",
            items=items,
            doc_type=self.doc_type,
            crawled_at=crawled_at,
            id_key=self.id_key,
            name_key=self.name_key,
            status_key=self.status_key,
            errors="\n".join(errors[:5]),
        )

    # ── 직전 스냅샷 로더 (서브클래스 폴백 빌딩블록) ──
    def _load_previous_snapshot(self) -> list[dict]:
        """가장 최근 일자별 스냅샷의 data 리스트 반환. 없으면 [].

        서브클래스의 `_curated_fallback` 이 첫 실행 직전 데이터를 재사용하고
        싶을 때 호출한다.
        """
        if not self.snapshot_dir.exists():
            return []
        snaps = sorted(self.snapshot_dir.glob("*.json"))
        if not snaps:
            return []
        try:
            data = json.loads(snaps[-1].read_text(encoding="utf-8"))
            return list(data.get("data") or [])
        except Exception as e:
            logger.warning("[%s] previous snapshot 로드 실패: %s", self.crawler_name, e)
            return []
