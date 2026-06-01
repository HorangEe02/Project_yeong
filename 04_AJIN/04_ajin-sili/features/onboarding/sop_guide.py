"""
SOP(표준작업절차서) 단계별 가이드 엔진
- 8종 SOP를 data/knowledge_base/sops/*.json 에서 로드 (Feature C Sprint 1 P0 외부화)
- Streamlit/React UI용 단계 네비게이션 제공
- 각 단계별 체크리스트 + 주의사항 + 관련 용어
- Admin CRUD: backend/routers/admin.py 의 /admin/kb/sops/* endpoints
- citation_id 부착: Sprint 2 citation_enforcer 가 이 ID 로 출처 검증

호환성:
  - SOP_DATABASE 는 __getattr__ 를 통해 lazy load (호출자 zero touch).
  - mtime 캐싱 — admin 편집 후 다음 호출에서 즉시 반영.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SOPStep:
    """SOP 개별 단계"""
    step_number: int
    title: str
    description: str
    checklist: List[str] = field(default_factory=list)
    caution: str = ""
    related_terms: List[str] = field(default_factory=list)
    estimated_time: str = ""
    responsible: str = ""
    # v4.7 C-2 — 영문 페어 (1차 기계번역, 빈 문자열이면 KO fallback)
    title_en: str = ""
    caution_en: str = ""


@dataclass
class SOPDocument:
    """SOP 문서 전체"""
    sop_id: str
    title: str
    department: str
    category: str          # "설비", "품질", "안전", "생산"
    steps: List[SOPStep] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)
    related_sops: List[str] = field(default_factory=list)
    # v4.7 C-2 — 영문 페어
    title_en: str = ""
    department_en: str = ""
    category_en: str = ""
    citation_id: str = ""
    owner_department: str = ""
    reviewed_at: str = ""
    effective_date: str = ""
    version: str = ""
    status: str = "published"


def localized_sop_title(doc: "SOPDocument", language: str) -> str:
    """언어별 SOP 타이틀. en + title_en 있으면 그것, 없으면 KO 원본."""
    if language == "en" and doc.title_en:
        return doc.title_en
    return doc.title


def localized_step_title(step: "SOPStep", language: str) -> str:
    if language == "en" and step.title_en:
        return step.title_en
    return step.title


# ──────────────────────────────────────────────
# 디스크 로더 (Feature C Sprint 1 P0 — plan §27.2)
# ──────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOPS_DIR = REPO_ROOT / "data" / "knowledge_base" / "sops"

# 모듈 레벨 캐시 + mtime 추적. 동시성 보호용 lock.
_SOP_CACHE: Optional[Dict[str, SOPDocument]] = None
_SOP_CACHE_MTIMES: Dict[Path, float] = {}
_SOP_LOCK = threading.Lock()


def _dict_to_sop_doc(payload: Dict[str, Any]) -> SOPDocument:
    """JSON dict → SOPDocument. 알 수 없는 키는 무시 (citation_id 등 메타).

    `steps` 의 dict → SOPStep 변환도 수행.
    """
    sop_fields = {f.name for f in fields(SOPDocument)}
    clean = {k: v for k, v in payload.items() if k in sop_fields}
    steps_raw = clean.get("steps", []) or []
    clean["steps"] = [
        SOPStep(**{k: v for k, v in s.items() if k in {f.name for f in fields(SOPStep)}})
        for s in steps_raw
    ]
    return SOPDocument(**clean)


def _load_sops_from_disk(force: bool = False, include_unpublished: bool = False) -> Dict[str, SOPDocument]:
    """data/knowledge_base/sops/*.json → {sop_id: SOPDocument}.

    mtime 기반 캐싱 — 같은 파일 set + 같은 mtime 이면 캐시 그대로.
    `force=True` 면 무조건 reload.
    Runtime callers receive only ``status=published`` documents. Missing status
    is normalized to ``published`` for legacy JSON compatibility while the
    release verifier still fails missing metadata.
    """
    global _SOP_CACHE
    with _SOP_LOCK:
        if not SOPS_DIR.exists():
            logger.warning("SOPS_DIR 미존재: %s — 빈 dict 반환", SOPS_DIR)
            _SOP_CACHE = {}
            _SOP_CACHE_MTIMES.clear()
            return _SOP_CACHE

        current_mtimes = {p: p.stat().st_mtime for p in SOPS_DIR.glob("*.json")}
        if (
            not force
            and _SOP_CACHE is not None
            and current_mtimes == _SOP_CACHE_MTIMES
        ):
            return dict(_SOP_CACHE) if include_unpublished else {
                k: v for k, v in _SOP_CACHE.items() if v.status == "published"
            }

        new_cache: Dict[str, SOPDocument] = {}
        for path in current_mtimes:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                doc = _dict_to_sop_doc(payload)
                if doc.sop_id:
                    new_cache[doc.sop_id] = doc
                else:
                    logger.warning("SOP %s: sop_id 누락 — skip", path.name)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.error("SOP %s 로드 실패: %s", path.name, e)
        _SOP_CACHE = new_cache
        _SOP_CACHE_MTIMES.clear()
        _SOP_CACHE_MTIMES.update(current_mtimes)
        logger.info("SOP 디스크 로드: %d 건", len(_SOP_CACHE))
        return dict(_SOP_CACHE) if include_unpublished else {
            k: v for k, v in _SOP_CACHE.items() if v.status == "published"
        }


def __getattr__(name: str) -> Any:
    """모듈 레벨 lazy attribute (PEP 562).

    `from features.onboarding.sop_guide import SOP_DATABASE` 호출 시 매번 fresh dict 반환.
    admin 이 JSON 편집한 직후 다음 호출에서 즉시 반영.
    """
    if name == "SOP_DATABASE":
        return _load_sops_from_disk()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ──────────────────────────────────────────────
# 키워드 → SOP 매핑 (외부화 보류 — Sprint 5 KB 확장 시 검토)
# ──────────────────────────────────────────────

SOP_KEYWORD_MAP = {
    "금형 교체": "SOP-001",
    "금형 세팅": "SOP-001",
    "프레스 금형": "SOP-001",
    "용접 검사": "SOP-002",
    "너겟 검사": "SOP-002",
    "품질 검사": "SOP-002",
    "CNC 가공": "SOP-003",
    "EWP 가공": "SOP-003",
    "정밀 가공": "SOP-003",
    # v3.4: 업무 프로세스 SOP 키워드
    "PPAP": "SOP-PPAP",
    "생산부품승인": "SOP-PPAP",
    "양산 승인": "SOP-PPAP",
    "8D": "SOP-8D",
    "클레임 대응": "SOP-8D",
    "시정 조치": "SOP-8D",
    "ECN": "SOP-ECN",
    "설계변경": "SOP-ECN",
    "도면 변경": "SOP-ECN",
    "프레스 트라이": "SOP-PRESS-TRIAL",
    "시타 참관": "SOP-PRESS-TRIAL",
    "트라이 준비": "SOP-PRESS-TRIAL",
    "금형 입고": "SOP-MOLD-RECEIVE",
    "금형 검수": "SOP-MOLD-RECEIVE",
    "신규 금형": "SOP-MOLD-RECEIVE",
}


def find_sop_by_query(query: str) -> Optional[SOPDocument]:
    """사용자 질문에서 관련 SOP 검색"""
    sops = _load_sops_from_disk()
    query_lower = query.lower()
    for keyword, sop_id in SOP_KEYWORD_MAP.items():
        if keyword in query_lower or keyword.replace(" ", "") in query_lower.replace(" ", ""):
            return sops.get(sop_id)
    return None


def get_all_sops() -> List[SOPDocument]:
    """전체 SOP 목록"""
    return list(_load_sops_from_disk().values())


def get_all_sops_for_admin() -> List[SOPDocument]:
    """Return every SOP document, including draft and archived entries.

    Returns:
        list[SOPDocument]: All SOP documents loaded from repo-local JSON files.
    """

    return list(_load_sops_from_disk(include_unpublished=True).values())
