"""P3 D11 — 경쟁사·산업 트렌드 (외부 데이터 fetch).

데이터 소스:
  - DART OpenAPI (https://opendart.fss.or.kr/) — 동종업계 분기보고서 메타
  - KOTRA / 관세청 무역통계 (선택)
  - KAMA 자동차산업협회 페이지 스크랩 (선택)

DART_API_KEY env 미설정 시 graceful skip — fetch 결과 빈 list.
인덱싱 결과는 SQLite (industry_trend.db) 에 적재.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "industry_trend.db"

# 비교 대상 동종업계 5개사 — 자동차 부품 산업
DEFAULT_PEER_CORP_CODES: dict[str, str] = {
    # corp_code: company name
    "00126308": "현대모비스",
    "00282399": "한국타이어앤테크놀로지",
    "00150282": "만도",
    "00148717": "한온시스템",
    "01089641": "일진하이솔루스",
}

DART_API_URL = "https://opendart.fss.or.kr/api/list.json"


# ─────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────


def init_industry_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS industry_filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            corp_code TEXT NOT NULL,
            corp_name TEXT NOT NULL,
            rcept_no TEXT NOT NULL,
            report_nm TEXT,
            rcept_dt TEXT,
            keywords TEXT DEFAULT '',
            fetched_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_filings_corp ON industry_filings(corp_code);
        CREATE INDEX IF NOT EXISTS idx_filings_dt ON industry_filings(rcept_dt);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_filings_rcept ON industry_filings(rcept_no);
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# DART OpenAPI fetch
# ─────────────────────────────────────────────────────────────


def fetch_dart_filings(corp_codes: dict[str, str] | None = None,
                        days: int = 90) -> list[dict[str, Any]]:
    """동종업계 corp_code 별 최근 N일 DART 분기보고서 메타 fetch.

    DART_API_KEY 미설정 시 빈 list. 외부 호출 실패 시도 graceful skip.
    """
    import os

    api_key = (os.environ.get("DART_API_KEY") or "").strip()
    if not api_key:
        logger.debug("DART_API_KEY 미설정 — fetch skip")
        return []

    targets = corp_codes if corp_codes else DEFAULT_PEER_CORP_CODES
    end = datetime.now()
    start = end - timedelta(days=max(7, min(days, 365)))
    bgn_de = start.strftime("%Y%m%d")
    end_de = end.strftime("%Y%m%d")

    try:
        from features.compliance.infra._http import fetch_json
    except ImportError:
        return []

    out: list[dict[str, Any]] = []
    for corp_code, corp_name in targets.items():
        url = (
            f"{DART_API_URL}?crtfc_key={api_key}&corp_code={corp_code}"
            f"&bgn_de={bgn_de}&end_de={end_de}&page_count=20"
        )
        try:
            data = fetch_json(url)
        except Exception as e:
            logger.warning("DART fetch 실패 corp=%s: %s", corp_code, e)
            continue

        if data.get("status") != "000":
            # DART 응답 status 코드 — '000' 만 정상
            logger.debug("DART 응답 비정상 corp=%s status=%s", corp_code, data.get("status"))
            continue

        for r in data.get("list") or []:
            out.append({
                "corp_code": corp_code,
                "corp_name": corp_name,
                "rcept_no": str(r.get("rcept_no") or ""),
                "report_nm": str(r.get("report_nm") or ""),
                "rcept_dt": str(r.get("rcept_dt") or ""),
            })
    return out


def index_filings(filings: list[dict[str, Any]]) -> int:
    """fetch 결과 → industry_filings DB 적재 (UNIQUE rcept_no 기준 dedupe)."""
    if not filings:
        return 0
    init_industry_db()
    conn = sqlite3.connect(str(DB_PATH))
    inserted = 0
    for f in filings:
        try:
            keywords = _extract_keywords_from_report(f.get("report_nm", ""))
            conn.execute(
                """INSERT OR IGNORE INTO industry_filings
                   (corp_code, corp_name, rcept_no, report_nm, rcept_dt, keywords)
                   VALUES (?,?,?,?,?,?)""",
                (
                    f["corp_code"], f["corp_name"], f["rcept_no"],
                    f.get("report_nm", ""), f.get("rcept_dt", ""),
                    ",".join(keywords),
                ),
            )
            if conn.total_changes > 0:
                inserted += 1
        except sqlite3.Error:
            continue
    conn.commit()
    conn.close()
    return inserted


_KW_PATTERNS = (
    "관세", "REACH", "RoHS", "산안법", "탄소", "ESG", "EV",
    "배터리", "리콜", "환경", "안전", "공시",
)


def _extract_keywords_from_report(text: str) -> list[str]:
    return [kw for kw in _KW_PATTERNS if kw in (text or "")]


# ─────────────────────────────────────────────────────────────
# 트렌드 분석 — 우리 변경 vs 산업 평균
# ─────────────────────────────────────────────────────────────


def compare_change_to_industry(change: dict[str, Any]) -> dict[str, Any]:
    """ChangeRecord → 산업 트렌드 비교.

    Returns:
        {
            "change_keywords": [...],
            "matching_filings_count": int,
            "by_corp": [{corp_code, corp_name, count, sample_reports[]}],
            "industry_average_filings": float,
            "verdict": "industry_wide" | "company_specific" | "no_data",
            "available": bool,
        }
    """
    init_industry_db()

    # 변경 본문에서 키워드 추출
    body = " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:1000],
    ])
    change_keywords = _extract_keywords_from_report(body)

    if not change_keywords:
        return {
            "change_keywords": [],
            "matching_filings_count": 0,
            "by_corp": [],
            "industry_average_filings": 0.0,
            "verdict": "no_data",
            "available": False,
        }

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 키워드 overlap — 산업 공시에서 같은 키워드 등장 빈도
    matching: list[dict[str, Any]] = []
    by_corp: dict[str, dict[str, Any]] = {}
    for kw in change_keywords:
        rows = conn.execute(
            "SELECT * FROM industry_filings WHERE keywords LIKE ?",
            (f"%{kw}%",),
        ).fetchall()
        for r in rows:
            entry = by_corp.setdefault(r["corp_code"], {
                "corp_code": r["corp_code"],
                "corp_name": r["corp_name"],
                "count": 0,
                "sample_reports": [],
            })
            entry["count"] += 1
            if len(entry["sample_reports"]) < 3:
                entry["sample_reports"].append({
                    "rcept_no": r["rcept_no"],
                    "report_nm": r["report_nm"],
                    "rcept_dt": r["rcept_dt"],
                })
            matching.append(dict(r))

    # 사용 가능한 공시 데이터 자체가 없으면 → no_data
    total_filings = conn.execute(
        "SELECT COUNT(*) as n FROM industry_filings"
    ).fetchone()["n"]
    conn.close()

    if total_filings == 0:
        return {
            "change_keywords": change_keywords,
            "matching_filings_count": 0,
            "by_corp": [],
            "industry_average_filings": 0.0,
            "verdict": "no_data",
            "available": False,
        }

    # verdict 판정
    industry_average = (
        sum(c["count"] for c in by_corp.values()) / max(len(DEFAULT_PEER_CORP_CODES), 1)
    )
    verdict = "industry_wide" if industry_average >= 1.0 else "company_specific"

    return {
        "change_keywords": change_keywords,
        "matching_filings_count": len(matching),
        "by_corp": sorted(by_corp.values(), key=lambda x: -x["count"]),
        "industry_average_filings": round(industry_average, 1),
        "verdict": verdict,
        "available": True,
    }


def collection_stats() -> dict[str, int]:
    init_industry_db()
    conn = sqlite3.connect(str(DB_PATH))
    n = conn.execute("SELECT COUNT(*) as n FROM industry_filings").fetchone()[0]
    n_corps = conn.execute(
        "SELECT COUNT(DISTINCT corp_code) as n FROM industry_filings"
    ).fetchone()[0]
    conn.close()
    return {"total_filings": int(n), "corp_count": int(n_corps)}
