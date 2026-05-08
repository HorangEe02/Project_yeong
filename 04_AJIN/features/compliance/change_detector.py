"""
규제 변경 자동 감지 엔진 (v3.1, v3.5 인코딩 수정)
- 크롤링 전후 JSON diff 비교
- 신규/변경/삭제 항목 자동 감지
- 변경 이력 SQLite 영구 저장

NOTE: 기존 텍스트 diff 기능은 text_change_detector.py로 이동됨
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict
from pathlib import Path

CHANGE_DB_PATH = "data/compliance_changes.db"


def _safe_truncate(text: str, max_chars: int = 500) -> str:
    """v3.5: 멀티바이트 문자 안전 잘림.

    Python 문자열 슬라이싱은 코드포인트 단위이므로 대부분 안전하지만,
    합성 이모지/조합형 글자 중간 절단을 방지하기 위해 UTF-8 바이트 수 기반으로 제한한다.
    """
    if len(text) <= max_chars:
        return text
    # 문자 단위로 max_chars 만큼 자른 후 UTF-8 인코딩 크기가 과도하면 줄임
    truncated = text[:max_chars]
    # 유니코드 서로게이트 쌍 중간 절단 방지
    try:
        truncated.encode("utf-8")
    except UnicodeEncodeError:
        truncated = truncated[:-1]
    return truncated


def init_change_db():
    """변경 이력 DB 초기화 (v3.5: UTF-8 PRAGMA 추가)"""
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.execute("PRAGMA encoding='UTF-8'")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS regulation_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TEXT NOT NULL,
            regulation_type TEXT NOT NULL,
            change_type TEXT NOT NULL,
            item_id TEXT,
            item_title TEXT,
            old_value TEXT,
            new_value TEXT,
            severity TEXT DEFAULT 'info',
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT,
            acknowledged_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def detect_changes(
    regulation_type: str,
    old_data: List[Dict],
    new_data: List[Dict],
    id_field: str = "id",
    compare_fields: List[str] = None,
) -> List[Dict]:
    """두 데이터셋 간 변경 사항 감지"""
    changes = []

    old_map = {str(item.get(id_field, i)): item for i, item in enumerate(old_data)}
    new_map = {str(item.get(id_field, i)): item for i, item in enumerate(new_data)}

    old_ids = set(old_map.keys())
    new_ids = set(new_map.keys())

    for item_id in new_ids - old_ids:
        item = new_map[item_id]
        changes.append({
            "regulation_type": regulation_type,
            "change_type": "added",
            "item_id": item_id,
            "item_title": item.get("title", item.get("name", item.get("name_ko", str(item_id)))),
            "old_value": None,
            "new_value": _safe_truncate(json.dumps(item, ensure_ascii=False), 500),
            "severity": "warning",
        })

    for item_id in old_ids - new_ids:
        item = old_map[item_id]
        changes.append({
            "regulation_type": regulation_type,
            "change_type": "removed",
            "item_id": item_id,
            "item_title": item.get("title", item.get("name", item.get("name_ko", str(item_id)))),
            "old_value": _safe_truncate(json.dumps(item, ensure_ascii=False), 500),
            "new_value": None,
            "severity": "info",
        })

    for item_id in old_ids & new_ids:
        old_item = old_map[item_id]
        new_item = new_map[item_id]
        fields = compare_fields or list(set(old_item.keys()) | set(new_item.keys()))
        diffs = []
        for field in fields:
            old_val = str(old_item.get(field, ""))
            new_val = str(new_item.get(field, ""))
            if old_val != new_val:
                diffs.append(f"{field}: '{_safe_truncate(old_val, 50)}' -> '{_safe_truncate(new_val, 50)}'")
        if diffs:
            changes.append({
                "regulation_type": regulation_type,
                "change_type": "modified",
                "item_id": item_id,
                "item_title": new_item.get("title", new_item.get("name", new_item.get("name_ko", str(item_id)))),
                "old_value": "; ".join(diffs[:5]),
                "new_value": _safe_truncate(json.dumps(new_item, ensure_ascii=False), 500),
                "severity": "warning" if len(diffs) >= 3 else "info",
            })

    return changes


def save_changes(changes: List[Dict]):
    """변경 사항 DB 저장"""
    if not changes:
        return
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    now = datetime.now().isoformat()
    for ch in changes:
        conn.execute(
            "INSERT INTO regulation_changes (detected_at, regulation_type, change_type, item_id, item_title, old_value, new_value, severity) VALUES (?,?,?,?,?,?,?,?)",
            (now, ch["regulation_type"], ch["change_type"], ch.get("item_id", ""), ch.get("item_title", ""), ch.get("old_value"), ch.get("new_value"), ch.get("severity", "info")),
        )
    conn.commit()
    conn.close()


def get_recent_changes(limit: int = 20, unacknowledged_only: bool = False) -> List[Dict]:
    """최근 변경 이력 조회"""
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM regulation_changes"
    if unacknowledged_only:
        query += " WHERE acknowledged = 0"
    query += " ORDER BY detected_at DESC LIMIT ?"
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def acknowledge_change(change_id: int, user_id: str = ""):
    """변경 확인 처리"""
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.execute(
        "UPDATE regulation_changes SET acknowledged=1, acknowledged_by=?, acknowledged_at=? WHERE id=?",
        (user_id, datetime.now().isoformat(), change_id),
    )
    conn.commit()
    conn.close()


def get_change_stats() -> Dict:
    """변경 통계"""
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM regulation_changes").fetchone()[0]
    unack = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE acknowledged=0").fetchone()[0]
    added = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE change_type='added'").fetchone()[0]
    modified = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE change_type='modified'").fetchone()[0]
    removed = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE change_type='removed'").fetchone()[0]
    conn.close()
    return {"total": total, "unacknowledged": unack, "added": added, "modified": modified, "removed": removed}


def detect_crawl_changes(regulation_type: str, old_json_path: str, new_json_path: str, id_field: str = "id", items_key: str = None) -> List[Dict]:
    """크롤링 JSON 파일 비교 편의 함수"""
    old_path, new_path = Path(old_json_path), Path(new_json_path)
    if not old_path.exists() or not new_path.exists():
        return []
    try:
        old_data = json.loads(old_path.read_text(encoding="utf-8"))
        new_data = json.loads(new_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if items_key:
        old_data = old_data.get(items_key, old_data) if isinstance(old_data, dict) else old_data
        new_data = new_data.get(items_key, new_data) if isinstance(new_data, dict) else new_data
    if not isinstance(old_data, list):
        old_data = [old_data]
    if not isinstance(new_data, list):
        new_data = [new_data]
    return detect_changes(regulation_type, old_data, new_data, id_field=id_field)
