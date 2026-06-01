"""P4 D17 — What-if 정밀화: 재무 baseline + Scope 1/2/3 분리.

보안: SQL 식별자(테이블명) 인터폴레이션은 화이트리스트 정규식 검증만 통과한 경우에만
수행 — `_SAFE_IDENT_RE` 참고.

우선순위 (높은 confidence 우선):
  1. 내부 ERP CSV  (data/internal_baseline.csv)        confidence=0.95
  2. DART 재무제표 (industry_trend.fetch_dart_filings) confidence=0.75
  3. 산업 평균    (P3 D11 KAMA — 미수집 시 skip)       confidence=0.50
  4. 하드코딩      (P3 D10 default)                    confidence=0.30

캐시: data/financial_baseline_cache.json, TTL 30일.
DART API 키 미설정 / rate limit 시 graceful fallback (낮은 confidence + 사용자 안내).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# SQL 식별자 화이트리스트 — 테이블/컬럼 이름 인터폴레이션 시 사용
_SAFE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# P4.1 §2 — DART 재무제표 account 매칭 (회사·연도별 표기 다양성 대응)
# IFRS account_id (DART 응답의 구조화 식별자) 가 한글 표기 보다 안정적이라 우선.
_IFRS_REVENUE_IDS = {
    "ifrs-full_Revenue",
    "ifrs-full_RevenueFromContractsWithCustomers",
}
_IFRS_COGS_IDS = {
    "ifrs-full_CostOfSales",
}
# 한글 표기 부분매치 (IFRS id 가 없을 때 fallback)
_DART_REVENUE_KEYS = ("매출액", "수익(매출액)", "영업수익", "매출")
_DART_COGS_KEYS = ("매출원가", "용역원가")


def _match_dart_revenue(row: dict[str, Any]) -> bool:
    """매출액 인지 — IFRS account_id 우선, 부족 시 한글 부분매치 (`매출` ∧ ¬`원가`)."""
    aid = (row.get("account_id") or "").strip()
    if aid in _IFRS_REVENUE_IDS:
        return True
    nm = (row.get("account_nm") or "").strip()
    if "원가" in nm:
        return False
    return any(k in nm for k in _DART_REVENUE_KEYS)


def _match_dart_cogs(row: dict[str, Any]) -> bool:
    """매출원가 인지 — IFRS account_id 우선, 부족 시 한글 부분매치."""
    aid = (row.get("account_id") or "").strip()
    if aid in _IFRS_COGS_IDS:
        return True
    nm = (row.get("account_nm") or "").strip()
    return any(k in nm for k in _DART_COGS_KEYS)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CACHE_PATH = DATA_DIR / "financial_baseline_cache.json"
INTERNAL_CSV_PATH = DATA_DIR / "internal_baseline.csv"
CACHE_TTL_DAYS = 30

# 한전 2024 발전 평균 emission factor (kgCO2/kWh) — Scope 2
KEPCO_EMISSION_FACTOR = 0.4781


@dataclass
class Baseline:
    revenue_krw_mn: int = 0
    cogs_krw_mn: int = 0
    labor_share: float = 0.25
    emissions: dict[str, Any] = field(default_factory=dict)
    data_source: str = "hardcoded"  # erp | dart | industry_avg | hardcoded
    confidence: float = 0.30
    as_of: str = ""
    corp_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# 하드코딩 default (P3 와 동일)
HARDCODED = Baseline(
    revenue_krw_mn=100_000,
    cogs_krw_mn=70_000,
    labor_share=0.25,
    emissions={"scope_1": 0, "scope_2": 0, "scope_3": None,
               "source": "hardcoded_default"},
    data_source="hardcoded",
    confidence=0.30,
    as_of=datetime.now().date().isoformat(),
)


# ─────────────────────────────────────────────────────────────
# 캐시
# ─────────────────────────────────────────────────────────────


def _read_cache(corp_code: str) -> Baseline | None:
    if not CACHE_PATH.exists():
        return None
    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    entry = cache.get(corp_code or "_industry_avg_")
    if not entry:
        return None
    fetched_at = entry.get("__fetched_at")
    if not fetched_at:
        return None
    try:
        ts = datetime.fromisoformat(fetched_at)
    except ValueError:
        return None
    if datetime.now() - ts > timedelta(days=CACHE_TTL_DAYS):
        return None
    payload = {k: v for k, v in entry.items() if k != "__fetched_at"}
    try:
        return Baseline(**payload)
    except TypeError:
        return None


def _write_cache(corp_code: str, baseline: Baseline) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache: dict[str, Any] = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}
    payload = baseline.to_dict()
    payload["__fetched_at"] = datetime.now().isoformat()
    cache[corp_code or "_industry_avg_"] = payload
    try:
        CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("baseline 캐시 쓰기 실패: %s", e)


# ─────────────────────────────────────────────────────────────
# 데이터 소스
# ─────────────────────────────────────────────────────────────


def _from_internal_csv() -> Baseline | None:
    """내부 ERP CSV 우선순위 1.

    CSV 형식:
      revenue_krw_mn,cogs_krw_mn,labor_share,scope_1_tons,scope_2_tons,scope_3_tons,as_of
    """
    path_env = os.environ.get("INTERNAL_BASELINE_CSV")
    csv_path = Path(path_env) if path_env else INTERNAL_CSV_PATH
    if not csv_path.exists():
        return None
    try:
        with csv_path.open(encoding="utf-8", newline="") as f:
            row = next(csv.DictReader(f), None)
    except (OSError, csv.Error) as e:
        logger.warning("internal_baseline.csv 파싱 실패: %s", e)
        return None
    if not row:
        return None
    try:
        return Baseline(
            revenue_krw_mn=int(float(row.get("revenue_krw_mn") or 0)),
            cogs_krw_mn=int(float(row.get("cogs_krw_mn") or 0)),
            labor_share=float(row.get("labor_share") or 0.25),
            emissions={
                "scope_1": int(float(row.get("scope_1_tons") or 0)),
                "scope_2": int(float(row.get("scope_2_tons") or 0)),
                "scope_3": (
                    int(float(row.get("scope_3_tons")))
                    if (row.get("scope_3_tons") or "").strip() else None
                ),
                "source": "internal_erp",
            },
            data_source="erp",
            confidence=0.95,
            as_of=row.get("as_of") or datetime.now().date().isoformat(),
        )
    except (TypeError, ValueError) as e:
        logger.warning("internal_baseline.csv 변환 실패: %s", e)
        return None


def _from_dart(corp_code: str, *, fs_div: str = "OFS") -> Baseline | None:
    """DART 재무제표 fetch — corp_code 필수, DART_API_KEY 필수.

    fs_div: 'OFS' (별도재무제표, default) | 'CFS' (연결재무제표 — P5 §8).
    P3 D11 의 fetch_dart_filings 와 별개로 fnlttSinglAcntAll.json 단건 호출.
    실패 / rate limit / 빈 응답 시 None.
    """
    if not corp_code:
        return None
    api_key = (os.environ.get("DART_API_KEY") or "").strip()
    if not api_key:
        return None
    if fs_div not in ("OFS", "CFS"):
        fs_div = "OFS"
    try:
        import httpx
    except ImportError:
        return None
    try:
        r = httpx.get(
            "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
            params={
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bsns_year": str(datetime.now().year - 1),
                "reprt_code": "11011",   # 사업보고서
                "fs_div": fs_div,        # OFS 별도 / CFS 연결
            },
            timeout=10.0,
        )
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("DART 재무제표 fetch 실패: %s", e)
        return None
    if body.get("status") not in (None, "000"):
        return None
    rows = body.get("list") or []
    if not rows:
        return None

    # 매출액 + 매출원가 항목 추출 — P4.1 §2: IFRS account_id 우선 + 한글 부분매치
    revenue = 0
    cogs = 0
    for row in rows:
        amt_str = str(row.get("thstrm_amount") or "0").replace(",", "")
        try:
            amt = int(amt_str)
        except ValueError:
            continue
        # 백만원 단위로 환산 (DART 는 원 단위)
        amt_mn = amt // 1_000_000
        if revenue == 0 and _match_dart_revenue(row):
            revenue = amt_mn
        elif cogs == 0 and _match_dart_cogs(row):
            cogs = amt_mn
        if revenue and cogs:
            break
    if revenue == 0 and cogs == 0:
        return None

    # P5 §8 — CFS 연결재무제표는 별도 data_source 라벨 + 살짝 높은 confidence
    # (자회사 포함, 그룹 단위 신뢰도). OFS 는 P4.1 까지의 default 라벨 그대로 유지.
    if fs_div == "CFS":
        return Baseline(
            revenue_krw_mn=revenue,
            cogs_krw_mn=cogs or int(revenue * 0.7),
            labor_share=0.25,
            emissions={"scope_1": 0, "scope_2": 0, "scope_3": None,
                       "source": "dart_cfs_no_emission"},
            data_source="dart_cfs",
            confidence=0.80,
            as_of=datetime.now().date().isoformat(),
            corp_code=corp_code,
        )
    return Baseline(
        revenue_krw_mn=revenue,
        cogs_krw_mn=cogs or int(revenue * 0.7),
        labor_share=0.25,
        emissions={"scope_1": 0, "scope_2": 0, "scope_3": None,
                   "source": "dart_no_emission"},
        data_source="dart",
        confidence=0.75,
        as_of=datetime.now().date().isoformat(),
        corp_code=corp_code,
    )


# P5 §4 — 동종업체 corp_code (DART OpenAPI 등록번호).
# .env 의 INDUSTRY_PEER_CORP_CODES 로 오버라이드 가능 (CSV: "00164742,00126362,...").
INDUSTRY_PEER_CORP_CODES = (
    "00164742",  # 일진하이솔루스
    "00164779",  # 한국타이어앤테크놀로지
    "00126362",  # HL만도
    "00126369",  # 현대모비스
    "00164725",  # 한온시스템
)


def _peer_corp_codes() -> list[str]:
    raw = (os.environ.get("INDUSTRY_PEER_CORP_CODES") or "").strip()
    if raw:
        codes = [c.strip() for c in raw.split(",") if c.strip()]
        if codes:
            return codes
    return list(INDUSTRY_PEER_CORP_CODES)


def _from_industry_avg() -> Baseline | None:
    """P5 §4 — DART 동종업체 5개사 재무제표 평균 (3개 이상 fetch 성공 시 유효).

    DART_API_KEY 미설정 / 3개 미만 fetch 성공 시 None 반환 → hardcoded 폴백.
    P4.1 §10 의 정직성 정책 유지 — 실 데이터 부족 시 산업 평균 가짜 숫자 X.
    """
    api_key = (os.environ.get("DART_API_KEY") or "").strip()
    if not api_key:
        return None
    revenues: list[int] = []
    cogs_list: list[int] = []
    fetched_codes: list[str] = []
    for cc in _peer_corp_codes():
        try:
            b = _from_dart(cc)
        except Exception as e:
            logger.debug("peer DART fetch 실패 corp=%s: %s", cc, e)
            b = None
        if b is None:
            continue
        if b.revenue_krw_mn > 0:
            revenues.append(b.revenue_krw_mn)
        if b.cogs_krw_mn > 0:
            cogs_list.append(b.cogs_krw_mn)
        fetched_codes.append(cc)
    if len(revenues) < 3:
        # 데이터 부족 — 평균을 신뢰 못 함, hardcoded 로 폴백
        return None
    return Baseline(
        revenue_krw_mn=sum(revenues) // len(revenues),
        cogs_krw_mn=(sum(cogs_list) // len(cogs_list)) if cogs_list else 0,
        labor_share=0.25,
        emissions={"scope_1": 0, "scope_2": 0, "scope_3": None,
                   "source": f"industry_avg_{len(fetched_codes)}peers"},
        data_source="industry_avg",
        confidence=0.50,
        as_of=datetime.now().date().isoformat(),
    )


# ─────────────────────────────────────────────────────────────
# Scope 2 (전력) — facility_db.kwh_per_year 가용 시 자동 계산
# ─────────────────────────────────────────────────────────────


def _enrich_scope_2(baseline: Baseline) -> None:
    """facility_db 에서 kwh_per_year 합계 → Scope 2 emission tons 산출.

    보안: 테이블명은 sqlite_master 결과여도 동적 SQL 인터폴레이션 전 반드시
    `_SAFE_IDENT_RE` 화이트리스트 검증을 통과해야 함. 한글/공백/quoting-escape
    가 필요한 식별자는 자동으로 skip — false positive 보다 silent skip 이 안전.
    """
    try:
        from features.compliance.infra.facility_db import get_db as _facility_db
        conn = _facility_db()
        # facility_db 스키마는 다양 — kwh_per_year 컬럼 존재시만 시도
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [r[0] for r in rows]
        kwh_total = 0
        for t in table_names:
            # 화이트리스트 미통과 식별자는 skip (SQL injection 방어)
            if not isinstance(t, str) or not _SAFE_IDENT_RE.match(t):
                logger.debug("Scope 2 enrich — 안전하지 않은 테이블명 skip: %r", t)
                continue
            try:
                cols = [
                    r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()
                ]
                if "kwh_per_year" in cols:
                    row = conn.execute(
                        f"SELECT COALESCE(SUM(kwh_per_year),0) FROM {t}"
                    ).fetchone()
                    kwh_total += int(row[0] or 0)
            except sqlite3.OperationalError:
                continue
        conn.close()
        if kwh_total > 0:
            tons = int(kwh_total * KEPCO_EMISSION_FACTOR / 1000)
            baseline.emissions["scope_2"] = tons
            baseline.emissions["source"] = (
                baseline.emissions.get("source", "") + "+kepco_factor"
            ).lstrip("+")
    except Exception as e:
        logger.debug("Scope 2 enrich 실패: %s", e)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────


def get_baseline(
    corp_code: str | None = None,
    *,
    use_cache: bool = True,
    fs_div: str = "OFS",
) -> Baseline:
    """우선순위에 따라 baseline 반환. 모두 실패 시 hardcoded (confidence=0.30).

    P5 §8 — fs_div='CFS' 시 DART 연결재무제표로 fetch (회사 + 자회사 합산).
    cache key 가 OFS / CFS 별로 분리되어 양쪽 동시 보유 가능.
    """
    code = (corp_code or os.environ.get("DART_CORP_CODE") or "").strip()
    cache_key = code if fs_div == "OFS" else f"{code}::CFS"

    if use_cache:
        cached = _read_cache(cache_key)
        if cached:
            return cached

    sources: list[tuple[str, callable]] = [  # type: ignore[type-arg]
        ("internal_csv", lambda: _from_internal_csv()),
        ("dart", lambda: _from_dart(code, fs_div=fs_div)),
        ("industry_avg", lambda: _from_industry_avg()),
    ]
    for label, fn in sources:
        try:
            result = fn()
        except Exception as e:
            logger.warning("baseline source %s 예외: %s", label, e)
            result = None
        if result:
            _enrich_scope_2(result)
            _write_cache(cache_key, result)
            return result

    fallback = Baseline(**HARDCODED.to_dict())
    fallback.corp_code = code
    fallback.as_of = datetime.now().date().isoformat()
    _enrich_scope_2(fallback)
    return fallback


def clear_cache() -> None:
    if CACHE_PATH.exists():
        try:
            CACHE_PATH.unlink()
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────
# Scope 합산 헬퍼 (탄소세 시뮬에서 사용)
# ─────────────────────────────────────────────────────────────


def total_emissions_tons(
    baseline: Baseline,
    scopes: list[int] | None = None,
) -> int:
    """선택된 Scope 의 emission tons 합계. None 은 [1,2] default (Scope 3 미수집 보호)."""
    selected = scopes or [1, 2]
    total = 0
    e = baseline.emissions or {}
    if 1 in selected:
        total += int(e.get("scope_1") or 0)
    if 2 in selected:
        total += int(e.get("scope_2") or 0)
    if 3 in selected and e.get("scope_3") is not None:
        total += int(e.get("scope_3") or 0)
    return total
