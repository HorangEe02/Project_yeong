"""Jinja2 템플릿 헤더 주석에서 메타데이터 추출.

각 .j2 템플릿 파일 상단에 다음 형식의 주석 블록이 있다:

    {# usage_hint: "고객사 클레임에 D1~D8 8단계로 응답할 때" #}
    {# dept_recommend: ["품질보증팀", "품질관리팀"] #}
    {# required_vars: ["recipient", "claim_summary"] #}
    {# example_output: "8D-2026-014 / 부품 EWP-001 외경 부적합" #}
    {# var_metadata:
      - {name: "title", label_ko: "제목", required: true, group: "기본", placeholder: "예: ..."}
      ...
    #}

본 모듈은 이 주석 블록을 파싱해 dict 로 반환한다. B1 (카드 미리보기) + B2 (변수 입력 폼)
의 메타 데이터 단일 진실 원천.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# 단순 키-값 패턴 (한 줄 주석)
_KV_RE = re.compile(r"\{#\s*(\w+):\s*(.+?)\s*#\}", re.DOTALL)
# var_metadata 같은 다중 라인 블록
_BLOCK_RE = re.compile(r"\{#\s*var_metadata:\s*(.*?)\s*#\}", re.DOTALL)


def _try_parse_value(raw: str) -> Any:
    """JSON-like 문자열을 시도 파싱. 실패 시 원문 string 반환."""
    raw = raw.strip()
    # JSON 배열/객체
    if raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # 따옴표 두른 문자열
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    # boolean
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw


def _parse_var_metadata_block(block: str) -> list[dict[str, Any]]:
    """`var_metadata:` 블록의 - {name: ..., label_ko: ...} 라인들을 파싱."""
    items: list[dict[str, Any]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("- {") or not line.endswith("}"):
            continue
        body = line[3:-1]  # "- {" 와 "}" 제거
        item: dict[str, Any] = {}
        # key: value 페어 추출 (콤마는 따옴표 외부에서만)
        for match in re.finditer(
            r'(\w+):\s*(true|false|"[^"]*"|\'[^\']*\'|\[[^\]]*\])',
            body,
        ):
            key, raw_val = match.group(1), match.group(2)
            item[key] = _try_parse_value(raw_val)
        if item.get("name"):
            items.append(item)
    return items


def parse_template_metadata(j2_path: Path) -> dict[str, Any]:
    """템플릿 파일 헤더 주석에서 메타데이터를 추출.

    누락/형식 오류 필드는 기본값으로 채워 항상 동일 schema 반환.
    """
    if not j2_path.exists():
        return _empty_metadata()

    try:
        content = j2_path.read_text(encoding="utf-8")
    except Exception:
        return _empty_metadata()

    meta: dict[str, Any] = _empty_metadata()

    # 1) var_metadata 블록 — 우선 추출 (다중 라인이라 다른 KV 패턴과 충돌 방지)
    block_match = _BLOCK_RE.search(content)
    if block_match:
        meta["var_metadata"] = _parse_var_metadata_block(block_match.group(1))

    # 2) 단일 라인 KV — usage_hint, dept_recommend, required_vars, example_output
    for kv_match in _KV_RE.finditer(content):
        key, raw = kv_match.group(1), kv_match.group(2)
        if key == "var_metadata":
            continue  # 위에서 처리
        meta[key] = _try_parse_value(raw)

    return meta


def _empty_metadata() -> dict[str, Any]:
    return {
        "usage_hint": "",
        "dept_recommend": [],
        "required_vars": [],
        "example_output": "",
        "var_metadata": [],
    }


# ─────────────────────────────────────────────────────────────
# doc_type → template file name 매핑
# ─────────────────────────────────────────────────────────────

DOC_TYPE_TEMPLATE_MAP: dict[str, str] = {
    "8d_report": "8d_report_template.j2",
    "ecn": "ecn_template.j2",
    "ppap": "ppap_checklist_template.j2",
    "fmea": "fmea_process_template.j2",
    "msa": "msa_report_template.j2",
    "oem_email": "oem_email_template.j2",
    "internal_email": "internal_email_template.j2",
    "meeting_min": "meeting_minutes_template.j2",
    "weekly_report": "weekly_report_template.j2",
    "leave_request": "leave_request_template.j2",
    "business_trip_request": "business_trip_request_template.j2",
    "resignation_letter": "resignation_letter_template.j2",
    "personnel_notice": "personnel_notice_template.j2",
    "quote": "quote_template.j2",
    "travel_report": "travel_report_template.j2",
    "spc_report": "spc_report_template.j2",
}


def get_template_path(doc_type: str, templates_dir: Path) -> Path | None:
    """doc_type → 실제 .j2 파일 경로. 매핑 없으면 None."""
    filename = DOC_TYPE_TEMPLATE_MAP.get(doc_type)
    if not filename:
        return None
    path = templates_dir / filename
    return path if path.exists() else None
