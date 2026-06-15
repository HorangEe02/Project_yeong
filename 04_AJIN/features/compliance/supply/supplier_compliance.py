"""P2 D6 — 공급망 통합 (협력사·HS·자가진단·시뮬레이션·대체협력사).

DB:
  data/suppliers.db
    suppliers(supplier_id, name, tier, country, contact_email, contact_phone,
              annual_volume_krw_mn, compliance_score, last_self_assessed_at)
    supplier_components(id, supplier_id, component_code, hs_code,
                        unit_price_krw, qty_per_year)
    supplier_self_assessments(id, supplier_id, change_id, sent_at,
                              response_received_at, response_score, response_json, status)
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "suppliers.db"

# 공급망 키워드 — match_suppliers 가 사용
_SUPPLIER_KEYWORDS = (
    "관세", "tariff", "원산지", "USMCA", "IRA",
    "REACH", "RoHS", "화학", "SVHC", "크롬", "납",
    "EV", "배터리", "탄소", "CBAM",
)


def init_suppliers_db() -> None:
    """suppliers.db 초기화 (멱등)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier INTEGER DEFAULT 1,
            country TEXT DEFAULT 'KR',
            contact_email TEXT DEFAULT '',
            contact_phone TEXT DEFAULT '',
            annual_volume_krw_mn INTEGER DEFAULT 0,
            compliance_score INTEGER DEFAULT 0,
            last_self_assessed_at TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS supplier_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id TEXT REFERENCES suppliers(supplier_id),
            component_code TEXT,
            hs_code TEXT,
            unit_price_krw INTEGER DEFAULT 0,
            qty_per_year INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS supplier_self_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id TEXT REFERENCES suppliers(supplier_id),
            change_id INTEGER,
            sent_at TEXT NOT NULL,
            response_received_at TEXT DEFAULT '',
            response_score INTEGER DEFAULT 0,
            response_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'sent'
        );

        CREATE INDEX IF NOT EXISTS idx_components_supplier ON supplier_components(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_components_hs ON supplier_components(hs_code);
        CREATE INDEX IF NOT EXISTS idx_assess_supplier ON supplier_self_assessments(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_assess_change ON supplier_self_assessments(change_id);
    """)

    # P4 D16 — 2차/3차 협력사 그래프 마이그레이션 (멱등)
    for ddl in (
        "ALTER TABLE suppliers ADD COLUMN parent_supplier_id TEXT DEFAULT ''",
        "ALTER TABLE suppliers ADD COLUMN tier_depth INTEGER DEFAULT 1",
        "ALTER TABLE suppliers ADD COLUMN relation_type TEXT DEFAULT 'direct'",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_suppliers_parent ON suppliers(parent_supplier_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_suppliers_depth ON suppliers(tier_depth)"
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# CSV import
# ─────────────────────────────────────────────────────────────


def import_suppliers_csv(csv_text: str) -> dict[str, int]:
    """CSV 텍스트 → suppliers DB 적재 (replace 모드).

    예상 컬럼: supplier_id, name, tier, country, contact_email,
              annual_volume_krw_mn (필요)
              + 선택: contact_phone

    Returns:
        {imported: N, skipped: M, errors: list[str]}
    """
    init_suppliers_db()
    reader = csv.DictReader(io.StringIO(csv_text))
    out = {"imported": 0, "skipped": 0, "errors": []}

    conn = sqlite3.connect(str(DB_PATH))
    for row in reader:
        sid = (row.get("supplier_id") or "").strip()
        name = (row.get("name") or "").strip()
        if not sid or not name:
            out["skipped"] += 1
            out["errors"].append(f"row missing supplier_id/name: {dict(row)}")
            continue
        try:
            conn.execute(
                """INSERT OR REPLACE INTO suppliers
                   (supplier_id, name, tier, country, contact_email, contact_phone,
                    annual_volume_krw_mn, compliance_score, last_self_assessed_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    name,
                    int(row.get("tier") or 1),
                    (row.get("country") or "KR").strip(),
                    (row.get("contact_email") or "").strip(),
                    (row.get("contact_phone") or "").strip(),
                    int(row.get("annual_volume_krw_mn") or 0),
                    int(row.get("compliance_score") or 0),
                    (row.get("last_self_assessed_at") or "").strip(),
                ),
            )
            out["imported"] += 1
        except (sqlite3.Error, ValueError) as e:
            out["skipped"] += 1
            out["errors"].append(f"row {sid}: {e}")
    conn.commit()
    conn.close()
    return out


def import_components_csv(csv_text: str) -> dict[str, int]:
    """CSV → supplier_components 적재.

    예상 컬럼: supplier_id, component_code, hs_code, unit_price_krw, qty_per_year
    """
    init_suppliers_db()
    reader = csv.DictReader(io.StringIO(csv_text))
    out = {"imported": 0, "skipped": 0, "errors": []}

    conn = sqlite3.connect(str(DB_PATH))
    for row in reader:
        sid = (row.get("supplier_id") or "").strip()
        if not sid:
            out["skipped"] += 1
            continue
        try:
            conn.execute(
                """INSERT INTO supplier_components
                   (supplier_id, component_code, hs_code, unit_price_krw, qty_per_year)
                   VALUES (?,?,?,?,?)""",
                (
                    sid,
                    (row.get("component_code") or "").strip(),
                    (row.get("hs_code") or "").strip(),
                    int(row.get("unit_price_krw") or 0),
                    int(row.get("qty_per_year") or 0),
                ),
            )
            out["imported"] += 1
        except (sqlite3.Error, ValueError) as e:
            out["skipped"] += 1
            out["errors"].append(f"component for {sid}: {e}")
    conn.commit()
    conn.close()
    return out


# ─────────────────────────────────────────────────────────────
# 매칭 — change → 영향 협력사
# ─────────────────────────────────────────────────────────────


def _extract_hs_codes(text: str) -> list[str]:
    """본문에서 HS 코드 패턴 추출 (8708, 8708.10, 8708.10.20 형식)."""
    return re.findall(r"\b\d{4}(?:\.\d{2}(?:\.\d{2,3})?)?\b", text or "")


def _extract_supplier_keywords(text: str) -> list[str]:
    found = []
    for kw in _SUPPLIER_KEYWORDS:
        if kw in text:
            found.append(kw)
    return found


def match_suppliers(change: dict[str, Any], top_k: int = 20) -> list[dict[str, Any]]:
    """ChangeRecord → 영향 협력사 list.

    매칭 축 3개:
      1. HS 코드 — 변경 본문의 HS 코드 ∩ supplier_components.hs_code
      2. 공급망 키워드 — 변경 본문의 키워드 = country/관세/REACH/배터리 등
      3. 국가 — 변경의 affected_plants 가 해외면 해당 국가 협력사 우선
    """
    init_suppliers_db()
    body = " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:1000],
    ])
    hs_codes = _extract_hs_codes(body)
    keywords = _extract_supplier_keywords(body)

    if not hs_codes and not keywords:
        return []

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    matched_supplier_ids: set[str] = set()
    match_reason: dict[str, list[str]] = {}

    # HS 매칭
    for hs in hs_codes:
        # prefix 매칭 — '8708' 변경시 '8708.10.20' 도 매칭
        rows = conn.execute(
            "SELECT DISTINCT supplier_id FROM supplier_components WHERE hs_code LIKE ?",
            (f"{hs}%",),
        ).fetchall()
        for r in rows:
            sid = r["supplier_id"]
            matched_supplier_ids.add(sid)
            match_reason.setdefault(sid, []).append(f"HS {hs}")

    # 국가 매칭 — keywords 에 국가명 ('US', '미국', '중국', 'CN', 'EU' 등) 있으면
    country_codes: list[str] = []
    if "관세" in body or "USMCA" in body or "IRA" in body or "미국" in body:
        country_codes.append("US")
    if "EU" in body or "REACH" in body or "CBAM" in body or "유럽" in body:
        country_codes.append("EU")
    if "중국" in body or "CN" in body:
        country_codes.append("CN")
    for cc in country_codes:
        rows = conn.execute(
            "SELECT supplier_id FROM suppliers WHERE country = ?", (cc,)
        ).fetchall()
        for r in rows:
            sid = r["supplier_id"]
            matched_supplier_ids.add(sid)
            match_reason.setdefault(sid, []).append(f"국가 {cc}")

    # 결과 빌드
    out: list[dict[str, Any]] = []
    for sid in matched_supplier_ids:
        s = conn.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ?", (sid,)
        ).fetchone()
        if s is None:
            continue
        out.append({
            "supplier_id": sid,
            "name": s["name"],
            "tier": s["tier"],
            "country": s["country"],
            "contact_email": s["contact_email"],
            "annual_volume_krw_mn": s["annual_volume_krw_mn"],
            "compliance_score": s["compliance_score"],
            "match_reasons": match_reason.get(sid, []),
        })
    conn.close()

    # 정렬: tier asc, annual_volume desc — 핵심 1차 협력사 우선
    out.sort(key=lambda x: (x["tier"], -x["annual_volume_krw_mn"]))
    return out[:top_k]


# ─────────────────────────────────────────────────────────────
# 자가진단 폼 생성 + 발송
# ─────────────────────────────────────────────────────────────


def generate_self_assessment_form(change: dict[str, Any], supplier: dict[str, Any]) -> str:
    """협력사별 맞춤 자가진단 양식 (markdown).

    SMTP 발송 본문으로 사용. LLM 호출 없이 룰베이스 — 결정론적·빠름.
    """
    title = change.get("item_title") or "(제목 없음)"
    summary = change.get("summary_ko") or ""
    legal = change.get("legal_class") or []
    if isinstance(legal, str):
        try:
            legal = json.loads(legal)
        except json.JSONDecodeError:
            legal = []

    lines = [
        f"# AJIN 협력사 컴플라이언스 자가진단 요청",
        "",
        f"**수신**: {supplier.get('name', '(미상)')}  ·  공급사 ID: `{supplier.get('supplier_id', '')}`",
        f"**관련 규제 변경**: {title}",
        "",
        "## 변경 요약",
        f"{summary or '(요약 없음)'}",
        "",
    ]
    if legal:
        lines.append(f"**법적 분류**: {', '.join(legal)}")
        lines.append("")

    lines.extend([
        "## 자가진단 항목",
        "",
        "다음 5개 항목에 대해 **YES / NO / 부분 / N/A** 로 답변해 주세요:",
        "",
        "1. 본 규제 변경 사항을 인지하고 있습니까?",
        "2. 귀사의 제품·공정이 본 규제에 직접 영향을 받습니까?",
        "3. 영향이 있다면, 시행일 전 대응 계획이 수립되어 있습니까?",
        "4. 본 변경으로 인한 단가 조정 또는 공급 차질 가능성이 있습니까?",
        "5. AJIN 의 추가 지원 (양식 / 인증 / 비용 분담) 이 필요합니까?",
        "",
        "## 회신 방법",
        "",
        "- 회신 메일 본문에 1~5번 항목별 답변 + 부연설명 포함",
        "- 회신 마감: 발송일 + 14일",
        "- 미회신 시 자동 reminder 발송 (총 3회)",
        "",
        "본 자가진단은 AJIN 공급망 컴플라이언스 모니터링의 일환입니다.",
        "",
        "AJIN 구매팀",
    ])
    return "\n".join(lines)


def send_self_assessment_email(
    change_id: int,
    supplier_id: str,
    body_markdown: str,
    subject: str = "[AJIN] 컴플라이언스 자가진단 요청",
) -> dict[str, Any]:
    """SMTP 발송 + supplier_self_assessments 적재.

    SMTP 키 미설정 시 graceful skip — 실제 발송 X, DB 에는 'queued' 로 적재.
    """
    init_suppliers_db()
    now = datetime.now().isoformat()

    # SMTP 발송 — config 미설정 시 skip
    sent_via_smtp = False
    try:
        from config import (
            SMTP_HOST,
            SMTP_PORT,
            SMTP_USER,
            SMTP_PASSWORD,
        )
    except ImportError:
        SMTP_HOST = SMTP_USER = SMTP_PASSWORD = ""
        SMTP_PORT = 587

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    s = conn.execute(
        "SELECT contact_email, name FROM suppliers WHERE supplier_id = ?", (supplier_id,)
    ).fetchone()
    if s is None:
        conn.close()
        return {"ok": False, "error": f"supplier_id={supplier_id} 미존재"}

    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD and s["contact_email"]:
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body_markdown, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = s["contact_email"]
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(msg)
            sent_via_smtp = True
        except Exception as e:
            logger.warning("SMTP 발송 실패 supplier=%s: %s", supplier_id, e)

    status = "sent" if sent_via_smtp else "queued"

    cur = conn.execute(
        """INSERT INTO supplier_self_assessments
           (supplier_id, change_id, sent_at, status, response_json)
           VALUES (?,?,?,?,?)""",
        (supplier_id, change_id, now, status, json.dumps({"body": body_markdown[:500]})),
    )
    aid = int(cur.lastrowid)
    conn.commit()
    conn.close()

    return {"ok": True, "assessment_id": aid, "status": status, "sent_via_smtp": sent_via_smtp}


def parse_response(supplier_id: str, response_text: str) -> dict[str, Any]:
    """협력사 회신 메일 본문 파싱 → score 산출.

    간단한 룰: YES/NO/N/A 답변 추출. 5개 항목 중:
      - YES = +20점 (인지·대응 양호)
      - NO  = -10점 (대응 필요 신호)
      - 부분 = +10점
      - N/A = 0점

    실제 회신 형식이 자유서술이라 추출 정확도는 낮음 → 사람 검토 필수.
    """
    text = (response_text or "").upper()
    yes = len(re.findall(r"\bYES\b", text))
    no_count = len(re.findall(r"\bNO\b", text))
    partial = len(re.findall(r"부분", response_text))
    score = max(0, min(100, 50 + yes * 20 - no_count * 10 + partial * 10))
    return {
        "yes": yes,
        "no": no_count,
        "partial": partial,
        "score": score,
        "raw_excerpt": (response_text or "")[:500],
    }


def list_suppliers(
    tier: int | None = None,
    country: str | None = None,
    min_score: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """협력사 목록 — UI 검색·필터."""
    init_suppliers_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    sql = "SELECT * FROM suppliers WHERE compliance_score >= ?"
    params: list[Any] = [int(min_score)]
    if tier is not None:
        sql += " AND tier = ?"
        params.append(int(tier))
    if country:
        sql += " AND country = ?"
        params.append(country)
    sql += " ORDER BY tier ASC, annual_volume_krw_mn DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_supplier(supplier_id: str) -> dict[str, Any] | None:
    """협력사 1건 + 부품 list."""
    init_suppliers_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    s = conn.execute(
        "SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,)
    ).fetchone()
    if s is None:
        conn.close()
        return None
    components = conn.execute(
        "SELECT * FROM supplier_components WHERE supplier_id = ?",
        (supplier_id,),
    ).fetchall()
    conn.close()
    out = dict(s)
    out["components"] = [dict(c) for c in components]
    return out
