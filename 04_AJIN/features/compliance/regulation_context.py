"""v2.5: 규제 데이터 참조 모듈 — 기능 D 크롤링 데이터를 기능 B LLM 프롬프트에 주입

기능 B에서 규제 관련 문서 작성 시, 기능 D의 크롤링 JSON 데이터에서
해당 규제의 최신 정보를 추출하여 LLM 컨텍스트에 자동 삽입한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CRAWLED_DIR = DATA_DIR / "crawled"

# 규제 유형 → JSON 파일 + 메타데이터 매핑
_REGULATION_FILES = {
    "ISO/IATF":         ("iso_standards.json", "standards", "standard_id"),
    "EU 규제":          ("eu_regulations.json", "regulations", "reg_id"),
    "국내법규":          ("domestic_laws.json", "laws", "law_id"),
    "미국규제(IRA/관세)": ("global_trade.json", "regulations", "regulation_id"),
    "OEM 품질기준":      ("oem_quality.json", "standards", "standard_id"),
    "MSDS/화학물질":     ("msds_data.json", "records", "chemical_id"),
    "ESG/탄소":         ("carbon_esg.json", "regulations", "regulation_id"),
    "EV 배터리":        ("ev_battery.json", "standards", "standard_id"),
    "APQP":            ("apqp_process.json", "phases", "phase_id"),
}


def get_regulation_context(regulation_type: str, regulation_name: str = "",
                           max_items: int = 5, max_chars: int = 3000) -> str:
    """규제 유형과 이름으로 관련 규제 데이터를 검색하여 LLM 컨텍스트 문자열을 반환한다.

    Args:
        regulation_type: "ISO/IATF", "EU 규제", "국내법규" 등
        regulation_name: 특정 규제명 (비어있으면 해당 유형 전체)
        max_items: 최대 반환 항목 수
        max_chars: 최대 문자 수

    Returns:
        "[규제 참조 데이터]\n..." 형태의 컨텍스트 문자열
    """
    mapping = _REGULATION_FILES.get(regulation_type)
    if not mapping:
        # 유형명에 키워드 매칭 시도
        for key, val in _REGULATION_FILES.items():
            if any(k in regulation_type for k in key.split("/")):
                mapping = val
                break

    if not mapping:
        return ""

    filename, items_key, id_key = mapping
    fpath = CRAWLED_DIR / filename

    if not fpath.exists():
        return ""

    try:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""

    items = data.get(items_key, [])
    if not items:
        return ""

    # 이름으로 필터링 (있으면)
    if regulation_name:
        name_lower = regulation_name.lower()
        filtered = []
        for item in items:
            item_str = json.dumps(item, ensure_ascii=False).lower()
            if name_lower in item_str or any(
                name_lower in str(item.get(k, "")).lower()
                for k in ["name", "name_ko", "title_ko", "title", id_key]
            ):
                filtered.append(item)
        if filtered:
            items = filtered

    # 최대 항목 제한
    items = items[:max_items]

    # 컨텍스트 문자열 생성
    lines = [f"[규제 참조 데이터 — {regulation_type}]"]
    lines.append(f"출처: {filename} (크롤링 일시: {data.get('crawled_at', 'N/A')})")
    lines.append("")

    for i, item in enumerate(items, 1):
        item_lines = _format_item(item, id_key, i)
        lines.extend(item_lines)
        lines.append("")

    result = "\n".join(lines)

    # 최대 문자 수 제한
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... (이하 생략)"

    return result


def get_available_regulations() -> list[dict]:
    """사용 가능한 규제 데이터 목록을 반환한다 (UI 셀렉트박스용).

    Returns:
        [{"type": "ISO/IATF", "file": "iso_standards.json", "count": 15, "crawled_at": "..."}, ...]
    """
    available = []
    for reg_type, (filename, items_key, _) in _REGULATION_FILES.items():
        fpath = CRAWLED_DIR / filename
        if not fpath.exists():
            continue
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            count = len(data.get(items_key, []))
            crawled_at = data.get("crawled_at", "N/A")
            available.append({
                "type": reg_type,
                "file": filename,
                "count": count,
                "crawled_at": crawled_at,
            })
        except Exception:
            continue
    return available


def get_regulation_items(regulation_type: str) -> list[dict]:
    """특정 규제 유형의 전체 항목을 반환한다 (개별 선택용).

    Returns:
        [{"id": "...", "name": "...", "status": "..."}, ...]
    """
    mapping = _REGULATION_FILES.get(regulation_type)
    if not mapping:
        return []

    filename, items_key, id_key = mapping
    fpath = CRAWLED_DIR / filename
    if not fpath.exists():
        return []

    try:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get(items_key, [])
        result = []
        for item in items:
            item_id = item.get(id_key, "N/A")
            name = item.get("name", item.get("name_ko", item.get("title_ko", item_id)))
            status = item.get("status", item.get("compliance_status",
                     item.get("ajin_compliance_status", "")))
            result.append({"id": item_id, "name": name, "status": status})
        return result
    except Exception:
        return []


def inject_regulation_context(prompt: str, regulation_type: str,
                               regulation_name: str = "") -> str:
    """기존 프롬프트에 규제 참조 데이터를 주입한다.

    Args:
        prompt: 기존 LLM 프롬프트
        regulation_type: 규제 유형
        regulation_name: 규제명 (선택)

    Returns:
        규제 컨텍스트가 주입된 프롬프트
    """
    context = get_regulation_context(regulation_type, regulation_name)
    if not context:
        return prompt

    return f"""{prompt}

─── 아래는 아진산업의 크롤링된 최신 규제 데이터입니다. 보고서 작성 시 참조하세요. ───

{context}

─── 규제 참조 데이터 끝 ───"""


def _format_item(item: dict, id_key: str, idx: int) -> list[str]:
    """규제 항목을 가독성 있는 텍스트 라인으로 변환한다."""
    lines = []
    item_id = item.get(id_key, "N/A")
    name = item.get("name", item.get("name_ko", item.get("title_ko", "")))
    lines.append(f"--- [{idx}] {item_id}: {name} ---")

    # 주요 필드 추출
    _FIELDS = [
        ("status", "상태"), ("compliance_status", "준수 상태"),
        ("ajin_compliance_status", "준수 상태"), ("ajin_readiness", "준비 상태"),
        ("effective_date", "시행일"), ("version", "버전"),
        ("category", "분류"), ("authority", "발행 기관"),
        ("ajin_relevance", "아진 관련성"),
    ]
    for key, label in _FIELDS:
        val = item.get(key)
        if val and val != "N/A":
            lines.append(f"  {label}: {val}")

    # 핵심 요구사항 (간략)
    reqs = item.get("key_requirements", item.get("key_requirements_ko", []))
    if reqs and isinstance(reqs, list):
        lines.append("  핵심 요구사항:")
        for r in reqs[:3]:
            if isinstance(r, dict):
                title = r.get("requirement", r.get("title", r.get("title_ko", "")))
                lines.append(f"    - {title}")
            elif isinstance(r, str):
                lines.append(f"    - {r}")

    # 조치 항목
    actions = item.get("action_items", item.get("action_items_ko", []))
    if actions and isinstance(actions, list):
        lines.append("  필요 조치:")
        for a in actions[:3]:
            text = str(a) if isinstance(a, str) else a.get("action", a.get("description", str(a)))
            lines.append(f"    - {text}")

    return lines
