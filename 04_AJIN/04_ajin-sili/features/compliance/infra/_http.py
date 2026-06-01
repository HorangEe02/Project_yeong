"""Phase 1 크롤러 공용 HTTP 유틸리티.

세 가지를 한곳에서 처리한다:
1. httpx 단일 클라이언트 + tenacity 재시도 백오프
2. robots.txt 준수 검사 (도메인당 1시간 캐시)
3. 도메인당 rate limit (1 req/s) — 서버 ToS 보호

크롤러는 직접 httpx 를 만들지 말고 이 모듈의 `fetch()` / `fetch_json()` /
`fetch_pdf()` 만 사용한다.
"""
from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser
from typing import Any
from urllib.parse import urlsplit

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

USER_AGENT = "AjinComplianceCrawler/1.0 (+contact@ajin.co.kr)"
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def get_client() -> httpx.Client:
    """프로세스 단위 단일 httpx.Client — 연결 풀링."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    timeout=DEFAULT_TIMEOUT,
                    follow_redirects=True,
                    headers={"User-Agent": USER_AGENT},
                )
    return _client


# ── 도메인별 rate limit (1 req/s) ──
_last_hit: dict[str, float] = {}
_rate_lock = threading.Lock()
_MIN_INTERVAL_SEC = 1.0


def _wait_rate_limit(host: str) -> None:
    with _rate_lock:
        last = _last_hit.get(host, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < _MIN_INTERVAL_SEC:
            time.sleep(_MIN_INTERVAL_SEC - elapsed)
        _last_hit[host] = time.monotonic()


# ── robots.txt 캐시 (도메인당 1시간) ──
_robots_cache: dict[str, tuple[urllib.robotparser.RobotFileParser, float]] = {}
_robots_lock = threading.Lock()
_ROBOTS_TTL_SEC = 3600.0


def check_robots(url: str) -> bool:
    """url 이 robots.txt 상 접근 가능한지 확인. 실패 시 보수적으로 True 반환.

    한국 정부 OpenAPI 들은 robots.txt 가 없거나 모든 봇을 허용하는 게 일반적.
    실패 시 False 반환하면 정상 호출도 막히므로, 명시적 disallow 만 거른다.
    """
    parts = urlsplit(url)
    host = f"{parts.scheme}://{parts.netloc}"
    now = time.monotonic()

    with _robots_lock:
        cached = _robots_cache.get(host)
        if cached and (now - cached[1]) < _ROBOTS_TTL_SEC:
            rp = cached[0]
        else:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{host}/robots.txt")
            try:
                rp.read()
            except Exception as e:
                logger.debug("robots.txt 로드 실패 (%s) — 허용으로 폴백: %s", host, e)
                rp = None  # type: ignore[assignment]
            _robots_cache[host] = (rp, now)  # type: ignore[assignment]

    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


# ── 재시도 가능한 fetch 함수들 ──
_RETRY_DECORATOR = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


@_RETRY_DECORATOR
def fetch(
    url: str,
    *,
    etag: str | None = None,
    use_cache: bool = False,
    **kwargs: Any,
) -> httpx.Response:
    """원시 GET 요청. ETag 캐시 헤더 자동 추가. 4xx/5xx 는 raise_for_status().

    F9 통합: `use_cache=True` 면 backend.services.http_cache 의 ETag/Last-Modified
    를 자동으로 읽어 If-None-Match / If-Modified-Since 헤더 첨부 + 응답 후 upsert.
    """
    if not check_robots(url):
        raise httpx.HTTPError(f"robots.txt 가 차단함: {url}")

    parts = urlsplit(url)
    _wait_rate_limit(parts.netloc)

    headers = dict(kwargs.pop("headers", {}))
    cached = None
    if use_cache:
        try:
            from backend.services.http_cache import get_cache
            cached = get_cache(url) or {}
            if cached.get("etag") and "If-None-Match" not in headers:
                headers["If-None-Match"] = cached["etag"]
            if cached.get("last_modified") and "If-Modified-Since" not in headers:
                headers["If-Modified-Since"] = cached["last_modified"]
        except Exception as e:
            logger.debug("http_cache 조회 실패 (%s) — cache miss 처리: %s", url, e)
    if etag and "If-None-Match" not in headers:
        headers["If-None-Match"] = etag

    resp = get_client().get(url, headers=headers, **kwargs)

    if use_cache:
        try:
            from backend.services.http_cache import upsert_cache
            new_etag = resp.headers.get("ETag", "") or (cached.get("etag", "") if cached else "")
            new_lm = resp.headers.get("Last-Modified", "") or (
                cached.get("last_modified", "") if cached else ""
            )
            if 200 <= resp.status_code < 300 or resp.status_code == 304:
                upsert_cache(url, new_etag, new_lm, resp.status_code)
        except Exception as e:
            logger.debug("http_cache upsert 실패 (%s): %s", url, e)

    if resp.status_code == 304:
        return resp
    resp.raise_for_status()
    return resp


def fetch_json(url: str, **kwargs: Any) -> Any:
    """GET → JSON 파싱. 실패 시 예외 전파."""
    resp = fetch(url, **kwargs)
    return resp.json()


def fetch_json_cached(url: str, **kwargs: Any) -> Any:
    """F9 — fetch_json + ETag 캐시 자동 통합. 304 시 None 반환 (caller 가 캐시 그대로 사용)."""
    kwargs["use_cache"] = True
    resp = fetch(url, **kwargs)
    if resp.status_code == 304:
        return None
    return resp.json()


def fetch_text(url: str, **kwargs: Any) -> str:
    resp = fetch(url, **kwargs)
    return resp.text


def fetch_bytes(url: str, **kwargs: Any) -> bytes:
    resp = fetch(url, **kwargs)
    return resp.content
