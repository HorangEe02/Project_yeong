"""MVP — 규제 변경 분류·요약·매핑·등급 (Stage 3 + 4 + 5).

`change_detector.detect_changes()` 가 만든 raw ChangeRecord dict 를 enrich:

  ChangeRecord (raw, from detect_changes)
      │
      ▼  classify_change()
  ChangeRecord (enriched)
      ├─ summary_ko       (한 줄 요약, 최대 80자)
      ├─ is_substantive   (실질적 의미 변경 여부)
      ├─ affected_departments  (룰베이스 매핑)
      ├─ affected_plants  (룰베이스 매핑)
      ├─ grade            (CRITICAL / HIGH / MEDIUM / LOW)
      └─ status           ('pending' or 'filtered')

설계 원칙:
  1. 룰 우선. LLM 은 보조 (이중 확인용).
  2. LLM 실패시 — 안전 쪽 폴백. 즉 "실질적 변경 / MEDIUM 등급" 처리해서
     알림 누락보다 알림 발생을 선호. (Compliance 도메인의 false negative
     비용이 false positive 보다 큼.)
  3. 노이즈 자동 archive — status='filtered' 로 DB 적재 후 사람 검색·복원 가능.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Stage 3 — 노이즈 필터 (룰 우선)
# ─────────────────────────────────────────────────────────────

# 비실질 변경 룰 — 본문 의미 그대로인 표면적 변경.
# 매칭되면 LLM 호출 없이 바로 noise 처리.
_NOISE_PATTERNS = [
    # 부칙 / 시행일 번호 변경 (날짜 자체 변경은 실질 → 제외)
    re.compile(r"^부칙\s*<제\d+호.*?>$"),
    # 띄어쓰기 / 구두점만 변경
    re.compile(r"^[\s.,;:'\"()/-]+$"),
    # 공백·hidden char 변경
    re.compile(r"^\s*$"),
]

# diff 본문 추출용 — change_detector.detect_changes 의 old_value 형식:
# "fieldA: 'old_short' -> 'new_short'; fieldB: '...' -> '...'"
_DIFF_FIELD_RE = re.compile(r"([\w_]+):\s*'(.*?)'\s*->\s*'(.*?)'(?:;|$)")


def _extract_diff_fields(old_value: str) -> list[tuple[str, str, str]]:
    """detect_changes 가 만든 old_value 문자열에서 (field, old, new) 추출."""
    return _DIFF_FIELD_RE.findall(old_value or "")


def is_substantive_change(change: dict) -> bool:
    """본 변경이 실질적 의미 변경인지 룰베이스 판단.

    True  — 알림·결재 대상
    False — 자동 archive (status='filtered')
    """
    # 신설/삭제는 항상 실질적.
    if change.get("change_type") in ("added", "removed"):
        return True

    # modified — diff 필드별 검사
    fields = _extract_diff_fields(change.get("old_value", ""))
    if not fields:
        # diff 형식 추출 실패 → 보수적으로 실질로 간주
        return True

    # 모든 필드 변경이 노이즈 패턴이면 비실질
    all_noise = True
    for _, old, new in fields:
        # 정규화 후 비교 — 공백·구두점 차이만이면 노이즈
        old_norm = re.sub(r"[\s.,;:'\"()/-]", "", old)
        new_norm = re.sub(r"[\s.,;:'\"()/-]", "", new)
        if old_norm != new_norm:
            all_noise = False
            break
        # 표면적 변경만 — 실제 내용 동일
    if all_noise:
        logger.debug("[noise] %s — 정규화 후 동일", change.get("item_id"))
        return False

    # 부칙 번호만 변경된 케이스 — 본문 무관
    for _, old, new in fields:
        if any(p.match(old) for p in _NOISE_PATTERNS) and any(
            p.match(new) for p in _NOISE_PATTERNS
        ):
            return False

    return True


# ─────────────────────────────────────────────────────────────
# Stage 3 — LLM 한 줄 요약 (Ollama 호출, 실패 시 룰베이스 폴백)
# ─────────────────────────────────────────────────────────────

_LLM_TIMEOUT_SEC = 8.0
_SUMMARY_MAX_CHARS = 80


def summarize_change(change: dict, llm_timeout: float = _LLM_TIMEOUT_SEC) -> str:
    """변경에 대한 한 줄 요약 (≤80자, 한국어).

    LLM (Ollama) 호출 실패시 → 룰베이스 템플릿 요약으로 폴백.
    """
    item_title = (change.get("item_title") or "").strip()
    change_type = change.get("change_type", "modified")
    old_value = (change.get("old_value") or "")[:300]
    new_value = (change.get("new_value") or "")[:300]

    # 룰베이스 폴백 요약 — 항상 사용 가능
    rule_summary = _rule_based_summary(item_title, change_type, old_value)

    # LLM 시도
    try:
        from config import OLLAMA_BASE_URL, LLM_MODEL, ollama_headers
    except ImportError:
        return rule_summary

    if not OLLAMA_BASE_URL:
        return rule_summary

    prompt = (
        f"다음 규제 변경을 한 줄(80자 이하)로 한국어 요약해.\n"
        f"제목: {item_title}\n"
        f"변경 유형: {change_type}\n"
        f"변경 내용: {old_value}\n"
        f"형식: 무엇이/얼마나 바뀌었는지 + (있으면) 영향. 80자 절대 초과 금지.\n"
        f"답변:"
    )
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            headers={**ollama_headers(), "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 100},
            },
            timeout=llm_timeout,
        )
        resp.raise_for_status()
        text = (resp.json().get("response") or "").strip()
        # 첫 줄만 + 길이 컷
        first_line = text.split("\n", 1)[0].strip()
        if first_line:
            return first_line[:_SUMMARY_MAX_CHARS]
    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        logger.warning("summarize_change LLM 실패: %s — 룰 폴백", e)

    return rule_summary


def _rule_based_summary(title: str, change_type: str, old_value: str) -> str:
    """LLM 미사용·실패 시 사용. 정보 손실 있어도 사용자에게 '없는 것보단 낫게' 제공."""
    title = (title or "(미상)").strip()
    if change_type == "added":
        return f"신설: {title}"[:_SUMMARY_MAX_CHARS]
    if change_type == "removed":
        return f"폐지: {title}"[:_SUMMARY_MAX_CHARS]
    # modified — diff 필드 1개만 표시
    fields = _extract_diff_fields(old_value)
    if fields:
        f, _, _ = fields[0]
        return f"개정: {title} — {f} 외 {max(0, len(fields)-1)}개 필드"[:_SUMMARY_MAX_CHARS]
    return f"개정: {title}"[:_SUMMARY_MAX_CHARS]


# ─────────────────────────────────────────────────────────────
# Stage 4 — 영향 매핑 (룰베이스, impact_network 재사용)
# ─────────────────────────────────────────────────────────────


def map_impact(change: dict) -> dict:
    """REGULATION_DEPT_MAP 키워드 매칭 → affected_departments / affected_plants.

    change dict 를 in-place 로 enrich + 그대로 반환.
    """
    from features.compliance.infra.impact_network import infer_departments

    title = change.get("item_title", "")
    body = (change.get("new_value") or change.get("old_value") or "")[:1000]
    description = body if body else ""

    departments = infer_departments(title, description)
    change["affected_departments"] = departments

    # 공장 매핑 — 본문에 plant_id 직접 등장하면 매칭. 없으면 빈 리스트.
    # 정밀도 우선: facility_db 의 plants.json 의 plant_id / name 키워드 매칭만 신뢰.
    plants: list[str] = []
    try:
        from pathlib import Path
        plant_json = Path(__file__).parent.parent.parent / "data" / "facility_db" / "plants.json"
        if plant_json.exists():
            plant_data = json.loads(plant_json.read_text(encoding="utf-8"))
            text_pool = f"{title} {body}".lower()
            for p in (plant_data.get("plants", []) +
                      plant_data.get("subsidiaries_domestic", []) +
                      plant_data.get("subsidiaries_overseas", [])):
                pid = p.get("plant_id", "") or p.get("subsidiary_id", "")
                pname = p.get("name", "")
                if pid and (pid.lower() in text_pool or pname.lower() in text_pool):
                    plants.append(pid)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    change["affected_plants"] = plants
    return change


# ─────────────────────────────────────────────────────────────
# Stage 5 — 등급 산출
# ─────────────────────────────────────────────────────────────


def assign_grade(change: dict) -> str:
    """변경의 grade 산출 → CRITICAL / HIGH / MEDIUM / LOW.

    룰:
      - change_type='added' (신설 의무)         → HIGH
      - change_type='removed' (의무 폐지)        → MEDIUM (대응 여유)
      - change_type='modified', diffs ≥ 3 + 키워드 hit → HIGH
      - change_type='modified', diffs ≥ 3       → MEDIUM
      - change_type='modified', diffs < 3        → LOW
      - severity='warning' 또는 영향 부서 ≥ 3개  → 등급 한 단계 상향
      - 처벌 키워드 (벌금/처벌/시행일/금지) hit  → 한 단계 상향
    """
    change_type = change.get("change_type", "modified")
    severity = (change.get("severity") or "info").lower()
    fields = _extract_diff_fields(change.get("old_value", ""))
    deps = change.get("affected_departments", [])

    body = f"{change.get('item_title','')} {change.get('new_value','') or ''}"
    has_penalty_keyword = any(
        kw in body for kw in ("벌금", "처벌", "징역", "과징금", "조업정지", "금지")
    )
    has_high_impact_keyword = any(
        kw in body for kw in ("관세", "REACH", "산안법", "OSHA", "CRITICAL", "긴급", "즉시")
    )

    # 기본 등급
    if change_type == "added":
        base = "HIGH"
    elif change_type == "removed":
        base = "MEDIUM"
    else:  # modified
        if len(fields) >= 3:
            base = "MEDIUM"
        elif len(fields) >= 1:
            base = "LOW"
        else:
            base = "LOW"

    # 상향 조건들
    grades = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    idx = grades.index(base)

    if severity == "warning":
        idx = min(len(grades) - 1, idx + 1)
    if len(deps) >= 3:
        idx = min(len(grades) - 1, idx + 1)
    if has_penalty_keyword:
        idx = min(len(grades) - 1, idx + 1)
    if has_high_impact_keyword:
        idx = min(len(grades) - 1, idx + 1)

    return grades[idx]


# ─────────────────────────────────────────────────────────────
# Pipeline orchestrator — Stage 3+4+5 한번에
# ─────────────────────────────────────────────────────────────


def classify_change(change: dict) -> dict:
    """단일 ChangeRecord 의 Stage 3 + 4 + 5 일괄 처리.

    BaseCrawler._run_diff() 가 detect_changes 결과 list 를 받아 각각 호출.
    """
    substantive = is_substantive_change(change)
    change["is_substantive"] = substantive

    if not substantive:
        # 노이즈 — DB 에는 적재하되 status='filtered' 로 자동 archive.
        # 사람이 변경 피드 페이지에서 "filtered 포함" 토글로 검색·복원 가능.
        change["status"] = "filtered"
        change["summary_ko"] = "[자동 분류: 비실질 변경]"
        change["grade"] = "LOW"
        change["affected_departments"] = []
        change["affected_plants"] = []
        return change

    # 실질 변경 — Stage 3+4+5 enrich
    change["summary_ko"] = summarize_change(change)
    map_impact(change)  # in-place
    change["grade"] = assign_grade(change)
    change["status"] = "pending"

    # P1 D1 — 법무 5분류 + 벌칙 조항 추출
    try:
        from features.compliance.alerts.legal_classifier import enrich_legal
        enrich_legal(change)  # in-place: legal_class, penalty_extract, penalty_severity_krw_mn
    except Exception as e:
        logger.warning("enrich_legal 실패: %s", e)
        change.setdefault("legal_class", [])
        change.setdefault("penalty_extract", "")
        change.setdefault("penalty_severity_krw_mn", 0)

    return change


def classify_batch(changes: list[dict]) -> list[dict]:
    """여러 변경 일괄 분류. 개별 실패는 swallow + LOW 폴백."""
    out: list[dict] = []
    for ch in changes:
        try:
            out.append(classify_change(ch))
        except Exception as e:
            logger.exception("classify_change 실패: item_id=%s", ch.get("item_id"))
            ch["is_substantive"] = True
            ch["summary_ko"] = f"[분류 실패: {type(e).__name__}]"
            ch["grade"] = "MEDIUM"
            ch["status"] = "pending"
            ch.setdefault("affected_departments", [])
            ch.setdefault("affected_plants", [])
            out.append(ch)
    return out
