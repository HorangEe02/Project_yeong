"""inspection_logs ETL 모듈 (v4.3 Phase 1).

CSV/XLSX 업로드 + PWA 제출 공통 적재 로직.
- Extract: csv.DictReader (BOM 허용) 또는 xlsx 파싱
- Transform: 한국어 별칭 정규화 + 검증 + JSON schema
- Load: 자연키 INSERT/UPDATE/SKIP + ingest_log 기록

스키마: docs/INSPECTION_CSV_SCHEMA.md
"""
from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

from backend.schemas.inspection_etl import IngestErrorRow, IngestResult
from core.data_lineage import ensure_lineage_columns, lineage_values
from features.equipment.inspection_db import INSPECTION_DB_PATH

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 한국어 별칭 매핑 (docs/INSPECTION_CSV_SCHEMA.md §7)
# ═══════════════════════════════════════════════════════════

_HEADER_ALIASES: dict[str, str] = {
    # equipment_id
    "equipment_id": "equipment_id",
    "설비id": "equipment_id", "설비코드": "equipment_id", "equipment id": "equipment_id",
    # equipment_name
    "equipment_name": "equipment_name",
    "설비명": "equipment_name", "equipment name": "equipment_name",
    # template_code
    "template_code": "template_code",
    "템플릿코드": "template_code", "점검유형": "template_code",
    # inspection_date
    "inspection_date": "inspection_date",
    "점검일": "inspection_date", "점검일자": "inspection_date",
    # inspector
    "inspector": "inspector",
    "검사자": "inspector", "점검자": "inspector",
    # overall_status
    "overall_status": "overall_status",
    "결과": "overall_status", "종합판정": "overall_status",
    # results_json
    "results_json": "results_json",
    "항목별결과": "results_json",
    # note
    "note": "note",
    "비고": "note", "메모": "note", "remark": "note",
}

_VALID_STATUS = {"PASS", "WARN", "FAIL"}


# ═══════════════════════════════════════════════════════════
# 테이블 보강 — ingest_log + unique index + source 컬럼
# ═══════════════════════════════════════════════════════════


def ensure_etl_tables(conn: sqlite3.Connection) -> None:
    """inspection ETL 용 테이블·인덱스·컬럼 멱등 생성."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_ingest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            source_label TEXT NOT NULL,
            file_name TEXT DEFAULT '',
            rows_total INTEGER DEFAULT 0,
            rows_inserted INTEGER DEFAULT 0,
            rows_updated INTEGER DEFAULT 0,
            rows_skipped INTEGER DEFAULT 0,
            rows_error INTEGER DEFAULT 0,
            error_payload TEXT DEFAULT '[]',
            actor TEXT NOT NULL
        )
        """
    )
    # source 컬럼 멱등 추가 — 합성/실 데이터 식별용 (Phase 4 마이그레이션 기준)
    try:
        conn.execute("ALTER TABLE inspection_logs ADD COLUMN source TEXT DEFAULT 'unknown'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE inspection_logs ADD COLUMN client_uuid TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    ensure_lineage_columns(conn, "inspection_logs")
    ensure_lineage_columns(conn, "inspection_ingest_log")
    seed_lineage = lineage_values("synthetic", "seed_equipment", "seed_equipment")
    conn.execute(
        """UPDATE inspection_logs
              SET data_class = ?,
                  source_system = ?,
                  source_label = CASE
                      WHEN source_label IS NULL OR source_label = '' THEN ?
                      ELSE source_label
                  END,
                  source_updated_at = CASE
                      WHEN source_updated_at IS NULL OR source_updated_at = '' THEN ?
                      ELSE source_updated_at
                  END
            WHERE source IN ('synthetic', 'seed_equipment', 'unknown', '', 'test')
              AND (data_class IS NULL OR data_class = '' OR data_class = 'unknown')""",
        (
            seed_lineage["data_class"],
            seed_lineage["source_system"],
            seed_lineage["source_label"],
            seed_lineage["source_updated_at"],
        ),
    )
    # 자연키 unique — Phase 4 마이그레이션 후 활성. 기존 합성 row 중복 가능성 있어
    # CREATE UNIQUE INDEX IF NOT EXISTS 는 실패 시 OperationalError 발생 → 무시.
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_natural "
            "ON inspection_logs(equipment_id, template_id, inspection_date, inspector)"
        )
    except sqlite3.OperationalError as e:
        logger.warning("[inspection_etl] unique index 미생성 (마이그레이션 필요): %s", e)
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_client_uuid "
            "ON inspection_logs(client_uuid) "
            "WHERE client_uuid IS NOT NULL AND client_uuid != ''"
        )
    except sqlite3.OperationalError as e:
        logger.warning("[inspection_etl] client_uuid unique index 미생성: %s", e)


# ═══════════════════════════════════════════════════════════
# 헬퍼 — header 정규화·검증
# ═══════════════════════════════════════════════════════════


def _normalize_header(raw: str) -> str | None:
    key = (raw or "").strip().lower().lstrip("﻿")
    return _HEADER_ALIASES.get(key)


def _normalize_row(raw_row: dict[str, Any], header_map: dict[str, str]) -> dict[str, Any]:
    """헤더 별칭 → 표준 컬럼명."""
    out: dict[str, Any] = {}
    for raw_key, std_key in header_map.items():
        out[std_key] = (raw_row.get(raw_key) or "").strip() if isinstance(raw_row.get(raw_key), str) else raw_row.get(raw_key)
    return out


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _lineage_for_source(source: str) -> dict[str, str]:
    """Map an inspection ingest source label to canonical lineage values.

    Args:
        source: Existing ETL source value such as ``csv_upload`` or ``tablet_pwa``.

    Returns:
        Canonical lineage dict for inspection rows.
    """
    source_key = (source or "unknown").strip().lower()
    if source_key in {"", "unknown", "test", "synthetic", "seed_equipment"}:
        return lineage_values("synthetic", "seed_equipment", source_key or "unknown")
    if source_key == "plc_ingest":
        return lineage_values("real", "plc_ingest", source_key)
    return lineage_values("real", "csv_upload" if source_key == "csv_upload" else source_key, source_key)


# ═══════════════════════════════════════════════════════════
# 검증 — 단일 row
# ═══════════════════════════════════════════════════════════


def _validate_row(
    row: dict[str, Any],
    template_lookup: dict[str, int],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """검증 통과 시 (정규화 dict, None, None). 실패 시 (None, error_code, error_msg)."""
    equipment_id = (row.get("equipment_id") or "").strip()
    if not equipment_id:
        return None, "EQUIPMENT_ID_EMPTY", "equipment_id 가 비어있습니다"
    if len(equipment_id) > 30:
        return None, "EQUIPMENT_ID_EMPTY", "equipment_id 30자 초과"

    template_code = (row.get("template_code") or "").strip()
    template_id = template_lookup.get(template_code)
    if template_id is None:
        return None, "UNKNOWN_TEMPLATE", f"template_code='{template_code}' 매칭 실패"

    insp_date_str = (row.get("inspection_date") or "").strip()
    try:
        insp_date = datetime.strptime(insp_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None, "INVALID_DATE", f"날짜 파싱 실패: '{insp_date_str}' (YYYY-MM-DD)"
    if insp_date > date.today():
        return None, "INVALID_DATE", f"미래 날짜 거부: {insp_date_str}"

    inspector = (row.get("inspector") or "").strip()
    if not inspector:
        return None, "INSPECTOR_EMPTY", "inspector 가 비어있습니다"
    inspector = inspector[:30]

    status = (row.get("overall_status") or "").strip().upper()
    if status not in _VALID_STATUS:
        return None, "INVALID_STATUS", f"overall_status='{status}' (PASS/WARN/FAIL 만 허용)"

    results_raw = row.get("results_json") or "[]"
    if isinstance(results_raw, str) and results_raw.strip():
        try:
            results = json.loads(results_raw)
            if not isinstance(results, list):
                raise ValueError("results_json 은 list 여야 함")
        except (json.JSONDecodeError, ValueError) as e:
            return None, "INVALID_JSON", f"results_json 파싱 실패: {e}"
    else:
        results = []

    equipment_name = (row.get("equipment_name") or "")[:100]
    note = (row.get("note") or "")[:500]

    return {
        "equipment_id": equipment_id,
        "equipment_name": equipment_name,
        "template_id": template_id,
        "inspection_date": insp_date.isoformat(),
        "inspector": inspector,
        "overall_status": status,
        "results_json": json.dumps(results, ensure_ascii=False),
        "note": note,
    }, None, None


# ═══════════════════════════════════════════════════════════
# 적재 — natural key 기반 INSERT / UPDATE / SKIP
# ═══════════════════════════════════════════════════════════


def _load_template_lookup(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT id, template_name FROM checklist_templates"
    ).fetchall()
    return {name: tid for tid, name in rows}


def _upsert_row(
    conn: sqlite3.Connection,
    normalized: dict[str, Any],
    source: str,
) -> Literal["inserted", "updated", "skipped"]:
    """자연키 (equipment_id, template_id, inspection_date, inspector) 기준 upsert.

    - 동일 자연키 row 없음 → INSERT
    - 있음 + results/note/status 같음 → SKIP
    - 있음 + 다름 → UPDATE
    """
    existing = conn.execute(
        """
        SELECT id, overall_status, results_json, note
        FROM inspection_logs
        WHERE equipment_id = ? AND template_id = ?
          AND inspection_date = ? AND inspector = ?
        LIMIT 1
        """,
        (
            normalized["equipment_id"],
            normalized["template_id"],
            normalized["inspection_date"],
            normalized["inspector"],
        ),
    ).fetchone()

    if existing is None:
        lineage = _lineage_for_source(source)
        conn.execute(
            """
            INSERT INTO inspection_logs
              (equipment_id, equipment_name, template_id, inspector,
               inspection_date, results_json, overall_status, note,
               created_at, source, data_class, source_system, source_label,
               source_updated_at, client_uuid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized["equipment_id"],
                normalized["equipment_name"],
                normalized["template_id"],
                normalized["inspector"],
                normalized["inspection_date"],
                normalized["results_json"],
                normalized["overall_status"],
                normalized["note"],
                _now_iso(),
                source,
                lineage["data_class"],
                lineage["source_system"],
                lineage["source_label"],
                lineage["source_updated_at"],
                normalized.get("client_uuid") or "",
            ),
        )
        return "inserted"

    _eid, ex_status, ex_results, ex_note = existing
    if (
        ex_status == normalized["overall_status"]
        and ex_results == normalized["results_json"]
        and (ex_note or "") == normalized["note"]
    ):
        return "skipped"

    lineage = _lineage_for_source(source)
    conn.execute(
        """
        UPDATE inspection_logs
        SET equipment_name = ?, results_json = ?, overall_status = ?, note = ?,
            source = ?, created_at = ?, data_class = ?, source_system = ?,
            source_label = ?, source_updated_at = ?,
            client_uuid = CASE
                WHEN ? != '' AND (client_uuid IS NULL OR client_uuid = '') THEN ?
                ELSE client_uuid
            END
        WHERE id = ?
        """,
        (
            normalized["equipment_name"],
            normalized["results_json"],
            normalized["overall_status"],
            normalized["note"],
            source,
            _now_iso(),
            lineage["data_class"],
            lineage["source_system"],
            lineage["source_label"],
            lineage["source_updated_at"],
            normalized.get("client_uuid") or "",
            normalized.get("client_uuid") or "",
            _eid,
        ),
    )
    return "updated"


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════


def parse_csv_bytes(data: bytes) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """UTF-8 (BOM 허용) CSV → rows + header_map (raw → standard)."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], {}

    header_map: dict[str, str] = {}
    for raw in reader.fieldnames:
        std = _normalize_header(raw)
        if std:
            header_map[raw] = std

    rows = list(reader)
    return rows, header_map


def _missing_required(header_map: dict[str, str]) -> list[str]:
    required = {"equipment_id", "template_code", "inspection_date", "inspector", "overall_status"}
    present = set(header_map.values())
    return sorted(required - present)


def ingest_csv(
    csv_bytes: bytes,
    *,
    source: str = "csv_upload",
    actor: str = "system",
    file_name: str = "",
    dry_run: bool = False,
    db_path: Path | None = None,
) -> IngestResult:
    """CSV bytes → IngestResult. dry_run 시 transaction rollback."""
    # 모듈 상수 lazy 해석 — 테스트 monkeypatch 호환 (기본값을 함수 정의 시점에
    # 캡처하면 monkeypatch 가 무력화되므로 호출 시점에 조회).
    if db_path is None:
        db_path = INSPECTION_DB_PATH
    started_at = _now_iso()
    rows, header_map = parse_csv_bytes(csv_bytes)
    missing = _missing_required(header_map)

    result = IngestResult(
        rows_total=len(rows),
        source=source,
        dry_run=dry_run,
        started_at=started_at,
        finished_at=started_at,
    )

    if missing:
        result.rows_error = len(rows)
        result.error_payload = [
            IngestErrorRow(
                row_index=0,
                error_code="MISSING_COLUMN",
                error_msg=f"필수 컬럼 누락: {', '.join(missing)}",
                raw_payload={},
            )
        ]
        result.finished_at = _now_iso()
        if not dry_run:
            _persist_log(db_path, result, file_name, actor)
        return result

    with sqlite3.connect(db_path) as conn:
        ensure_etl_tables(conn)
        template_lookup = _load_template_lookup(conn)
        for idx, raw in enumerate(rows, start=1):
            norm_row = _normalize_row(raw, header_map)
            validated, err_code, err_msg = _validate_row(norm_row, template_lookup)
            if validated is None:
                result.rows_error += 1
                if len(result.error_payload) < 50:
                    result.error_payload.append(IngestErrorRow(
                        row_index=idx,
                        error_code=err_code or "UNKNOWN",
                        error_msg=err_msg or "",
                        raw_payload={k: v for k, v in norm_row.items() if v is not None},
                    ))
                continue
            try:
                outcome = _upsert_row(conn, validated, source=source)
            except sqlite3.Error as e:
                result.rows_error += 1
                if len(result.error_payload) < 50:
                    result.error_payload.append(IngestErrorRow(
                        row_index=idx,
                        error_code="DB_ERROR",
                        error_msg=str(e),
                    ))
                continue
            if outcome == "inserted":
                result.rows_inserted += 1
            elif outcome == "updated":
                result.rows_updated += 1
            else:
                result.rows_skipped += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
            _persist_log_inline(conn, result, file_name, actor)

    result.finished_at = _now_iso()
    return result


def _persist_log_inline(
    conn: sqlite3.Connection,
    result: IngestResult,
    file_name: str,
    actor: str,
) -> None:
    lineage = _lineage_for_source(result.source)
    cur = conn.execute(
        """
        INSERT INTO inspection_ingest_log
          (started_at, finished_at, source_label, file_name,
           rows_total, rows_inserted, rows_updated, rows_skipped, rows_error,
           error_payload, actor, data_class, source_system, source_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.started_at,
            _now_iso(),
            result.source,
            file_name,
            result.rows_total,
            result.rows_inserted,
            result.rows_updated,
            result.rows_skipped,
            result.rows_error,
            json.dumps(
                [e.model_dump() for e in result.error_payload],
                ensure_ascii=False,
            ),
            actor,
            lineage["data_class"],
            lineage["source_system"],
            lineage["source_updated_at"],
        ),
    )
    conn.commit()
    result.ingest_log_id = cur.lastrowid


def _persist_log(
    db_path: Path,
    result: IngestResult,
    file_name: str,
    actor: str,
) -> None:
    with sqlite3.connect(db_path) as conn:
        ensure_etl_tables(conn)
        _persist_log_inline(conn, result, file_name, actor)


# ═══════════════════════════════════════════════════════════
# PWA 단건 제출
# ═══════════════════════════════════════════════════════════


def submit_single(
    *,
    equipment_id: str,
    template_id: int,
    inspector: str,
    inspection_date: str | None,
    results: Iterable[dict[str, Any]],
    overall_status: str,
    note: str = "",
    client_uuid: str | None = None,
    source: str = "tablet_pwa",
    db_path: Path | None = None,
) -> tuple[int, bool]:
    """단건 적재 — 자연키 + (optional) client_uuid 중복 체크.

    Returns: (inspection_log_id, deduplicated)
    """
    if db_path is None:
        db_path = INSPECTION_DB_PATH
    insp_date = inspection_date or date.today().isoformat()
    results_json = json.dumps(list(results), ensure_ascii=False)
    normalized = {
        "equipment_id": equipment_id,
        "equipment_name": "",
        "template_id": template_id,
        "inspection_date": insp_date,
        "inspector": inspector[:30],
        "overall_status": overall_status,
        "results_json": results_json,
        "note": note[:500],
        "client_uuid": (client_uuid or "").strip()[:80],
    }
    with sqlite3.connect(db_path) as conn:
        ensure_etl_tables(conn)
        if normalized["client_uuid"]:
            row = conn.execute(
                """
                SELECT id FROM inspection_logs
                WHERE client_uuid = ?
                LIMIT 1
                """,
                (normalized["client_uuid"],),
            ).fetchone()
            if row is not None:
                return row[0], True
        outcome = _upsert_row(conn, normalized, source=source)
        if normalized["client_uuid"]:
            row = conn.execute(
                """
                SELECT id FROM inspection_logs
                WHERE client_uuid = ?
                LIMIT 1
                """,
                (normalized["client_uuid"],),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id FROM inspection_logs
                WHERE equipment_id = ? AND template_id = ?
                  AND inspection_date = ? AND inspector = ?
                LIMIT 1
                """,
                (equipment_id, template_id, insp_date, inspector[:30]),
            ).fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError("submit_single: 적재 row 미확인")
        return row[0], outcome == "skipped"


# ═══════════════════════════════════════════════════════════
# ingest_log 조회
# ═══════════════════════════════════════════════════════════


def list_ingest_logs(
    limit: int = 20,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    if db_path is None:
        db_path = INSPECTION_DB_PATH
    with sqlite3.connect(db_path) as conn:
        ensure_etl_tables(conn)
        rows = conn.execute(
            """
            SELECT id, started_at, finished_at, source_label, file_name,
                   rows_total, rows_inserted, rows_updated, rows_skipped,
                   rows_error, actor
            FROM inspection_ingest_log
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "started_at": r[1],
            "finished_at": r[2],
            "source_label": r[3],
            "file_name": r[4],
            "rows_total": r[5],
            "rows_inserted": r[6],
            "rows_updated": r[7],
            "rows_skipped": r[8],
            "rows_error": r[9],
            "actor": r[10],
        }
        for r in rows
    ]
