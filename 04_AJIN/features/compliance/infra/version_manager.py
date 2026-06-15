"""v2.3: 규제 크롤링 버전 관리 — Before/After 비교 지원

크롤링 실행 전 기존 JSON을 history/ 디렉토리에 타임스탬프 백업하고,
두 버전의 규제 데이터를 비교하여 추가/삭제/변경 항목을 반환한다.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


CRAWLED_DIR = Path(__file__).parent.parent.parent / "data" / "crawled"
HISTORY_DIR = CRAWLED_DIR / "history"


def backup_before_crawl(json_filename: str) -> Path | None:
    """크롤링 실행 전 기존 JSON을 history/ 디렉토리에 백업한다.

    Returns:
        백업 파일 경로 (기존 파일이 없으면 None)
    """
    src = CRAWLED_DIR / json_filename
    if not src.exists():
        return None

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(json_filename).stem
    backup_name = f"{stem}_{timestamp}.json"
    dst = HISTORY_DIR / backup_name

    shutil.copy2(src, dst)
    return dst


def list_versions(json_filename: str) -> list[dict]:
    """특정 규제 JSON의 백업 버전 목록을 반환한다.

    Returns:
        [{"filename": "xxx_20260326_120000.json", "date": "2026-03-26 12:00:00", "size": 12345}, ...]
    """
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(json_filename).stem

    versions = []
    for f in sorted(HISTORY_DIR.glob(f"{stem}_*.json"), reverse=True):
        # 타임스탬프 추출: stem_YYYYMMDD_HHMMSS.json
        parts = f.stem.split("_")
        if len(parts) >= 3:
            try:
                date_str = parts[-2]
                time_str = parts[-1]
                dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                versions.append({
                    "filename": f.name,
                    "path": str(f),
                    "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "size": f.stat().st_size,
                })
            except (ValueError, IndexError):
                pass

    return versions[:20]  # 최근 20개까지


def compare_versions(json_filename: str, old_path: str | None = None) -> dict:
    """현재 버전과 이전 버전을 비교하여 변경 사항을 반환한다.

    Args:
        json_filename: 현재 JSON 파일명 (예: "domestic_laws.json")
        old_path: 비교할 이전 버전 파일 경로. None이면 가장 최근 백업과 비교.

    Returns:
        {
            "added": [{"id": ..., "name": ...}, ...],
            "removed": [{"id": ..., "name": ...}, ...],
            "modified": [{"id": ..., "name": ..., "changes": [...]}, ...],
            "unchanged_count": int,
            "current_date": str,
            "previous_date": str,
        }
    """
    current_path = CRAWLED_DIR / json_filename

    if not current_path.exists():
        return {"error": "현재 버전 파일이 없습니다."}

    # 이전 버전 결정
    if old_path:
        prev_path = Path(old_path)
    else:
        versions = list_versions(json_filename)
        if not versions:
            return {"error": "이전 버전이 없습니다. 첫 크롤링 후 비교 가능합니다."}
        prev_path = Path(versions[0]["path"])

    if not prev_path.exists():
        return {"error": f"이전 버전 파일을 찾을 수 없습니다: {prev_path.name}"}

    try:
        current_data = json.loads(current_path.read_text(encoding="utf-8"))
        previous_data = json.loads(prev_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"JSON 파싱 오류: {e}"}

    # 규제 항목 리스트 추출 (JSON 구조에 따라 키가 다름)
    current_items = _extract_items(current_data)
    previous_items = _extract_items(previous_data)

    # ID 기반 비교
    current_map = {_get_item_id(item): item for item in current_items}
    previous_map = {_get_item_id(item): item for item in previous_items}

    current_ids = set(current_map.keys())
    previous_ids = set(previous_map.keys())

    added_ids = current_ids - previous_ids
    removed_ids = previous_ids - current_ids
    common_ids = current_ids & previous_ids

    added = [_summarize_item(current_map[id_]) for id_ in sorted(added_ids)]
    removed = [_summarize_item(previous_map[id_]) for id_ in sorted(removed_ids)]

    modified = []
    unchanged_count = 0
    for id_ in sorted(common_ids):
        changes = _diff_items(previous_map[id_], current_map[id_])
        if changes:
            modified.append({
                **_summarize_item(current_map[id_]),
                "changes": changes,
            })
        else:
            unchanged_count += 1

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged_count": unchanged_count,
        "current_date": current_data.get("crawled_at", "N/A"),
        "previous_date": previous_data.get("crawled_at", "N/A"),
        "current_total": len(current_items),
        "previous_total": len(previous_items),
    }


def _extract_items(data: dict) -> list[dict]:
    """JSON 데이터에서 규제 항목 리스트를 추출한다."""
    _ITEM_KEYS = [
        "laws", "standards", "regulations", "records",
        "phases", "checklists", "updates",
    ]
    items = []
    for key in _ITEM_KEYS:
        if key in data and isinstance(data[key], list):
            items.extend(data[key])
    return items


def _get_item_id(item: dict) -> str:
    """항목의 고유 ID를 반환한다."""
    _ID_FIELDS = [
        "law_id", "standard_id", "reg_id", "regulation_id",
        "chemical_id", "phase_id", "checklist_id", "update_id",
        "id", "name",
    ]
    for field in _ID_FIELDS:
        if field in item and item[field]:
            return str(item[field])
    return str(hash(json.dumps(item, sort_keys=True, ensure_ascii=False)))


def _summarize_item(item: dict) -> dict:
    """항목의 요약 정보를 반환한다."""
    name = item.get("name", item.get("name_ko", item.get("title_ko", "")))
    id_ = _get_item_id(item)
    status = item.get("compliance_status", item.get("ajin_compliance_status", item.get("status", "")))
    return {"id": id_, "name": name, "status": status}


def _diff_items(old: dict, new: dict) -> list[str]:
    """두 항목의 필드 차이를 반환한다."""
    changes = []
    _COMPARE_FIELDS = [
        "name", "name_ko", "compliance_status", "ajin_compliance_status",
        "ajin_readiness", "status", "last_amended", "version",
        "effective_date", "next_review", "category",
    ]
    for field in _COMPARE_FIELDS:
        old_val = old.get(field, "")
        new_val = new.get(field, "")
        if str(old_val) != str(new_val) and (old_val or new_val):
            changes.append(f"`{field}`: {old_val or '(없음)'} → {new_val or '(없음)'}")
    return changes
