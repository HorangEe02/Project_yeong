"""
부서 간 협업 시나리오 가이드 (Feature C Sprint 1 P0 외부화).

데이터 출처:
  - data/knowledge_base/collaboration/*.json (Sprint 1 외부화, 5건 시드)
  - core/scenarios DB (기존 동적 시나리오, match_collaboration 우선 조회)

호출 호환:
  - COLLABORATION_SCENARIOS list 는 __getattr__ 로 lazy load (호출자 zero touch).
  - match_collaboration / format_collaboration_response 시그니처 보존.

citation_id 부착: Sprint 2 citation_enforcer 가 이 ID 로 출처 검증.
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
class CollaborationScenario:
    """부서 간 협업 시나리오"""
    id: str
    trigger_keywords: List[str]
    situation: str
    requesting_dept: str
    my_actions: List[str]
    hand_off_to: str
    hand_off_items: List[str]
    deadline_info: str
    related_sop_id: str = ""
    tips: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# 디스크 로더 (Feature C Sprint 1 P0 — plan §27.2)
# ──────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COLLAB_DIR = REPO_ROOT / "data" / "knowledge_base" / "collaboration"

_COLLAB_CACHE: Optional[List[CollaborationScenario]] = None
_COLLAB_CACHE_MTIMES: Dict[Path, float] = {}
_COLLAB_LOCK = threading.Lock()


def _dict_to_scenario(payload: Dict[str, Any]) -> Optional[CollaborationScenario]:
    """JSON dict → CollaborationScenario. 알 수 없는 키는 무시 (citation_id 등 메타)."""
    cs_fields = {f.name for f in fields(CollaborationScenario)}
    clean = {k: v for k, v in payload.items() if k in cs_fields}
    if not clean.get("id"):
        return None
    return CollaborationScenario(**clean)


def _load_collab_from_disk(force: bool = False) -> List[CollaborationScenario]:
    """data/knowledge_base/collaboration/*.json → List[CollaborationScenario].

    mtime 기반 캐싱. JSON 파일 명세는 id 필드 필수.
    """
    global _COLLAB_CACHE
    with _COLLAB_LOCK:
        if not COLLAB_DIR.exists():
            logger.warning("COLLAB_DIR 미존재: %s — 빈 list 반환", COLLAB_DIR)
            _COLLAB_CACHE = []
            _COLLAB_CACHE_MTIMES.clear()
            return _COLLAB_CACHE

        current_mtimes = {p: p.stat().st_mtime for p in COLLAB_DIR.glob("*.json")}
        if (
            not force
            and _COLLAB_CACHE is not None
            and current_mtimes == _COLLAB_CACHE_MTIMES
        ):
            return _COLLAB_CACHE

        new_cache: List[CollaborationScenario] = []
        for path in sorted(current_mtimes):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                doc = _dict_to_scenario(payload)
                if doc is not None:
                    new_cache.append(doc)
                else:
                    logger.warning("COLLAB %s: id 누락 — skip", path.name)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.error("COLLAB %s 로드 실패: %s", path.name, e)
        _COLLAB_CACHE = new_cache
        _COLLAB_CACHE_MTIMES.clear()
        _COLLAB_CACHE_MTIMES.update(current_mtimes)
        logger.info("COLLAB 디스크 로드: %d 건", len(_COLLAB_CACHE))
        return _COLLAB_CACHE


def __getattr__(name: str) -> Any:
    """모듈 레벨 lazy attribute (PEP 562).

    `from features.onboarding.collaboration_guide import COLLABORATION_SCENARIOS`
    호출 시 매번 fresh list 반환. admin 편집 후 다음 호출에서 반영.
    """
    if name == "COLLABORATION_SCENARIOS":
        return _load_collab_from_disk()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ──────────────────────────────────────────────
# 매칭 / 포맷 helpers (호환 보존)
# ──────────────────────────────────────────────


def match_collaboration(
    query: str, division: str = "", lang: str = "ko"
) -> Optional[CollaborationScenario]:
    """사용자 질문에서 협업 시나리오 매칭.

    DB(scenarios.db) 우선, 비어있으면 디스크 시드 사용.
    Phase 2: division/lang 컨텍스트 적용.
    """
    # DB 우선 — repository.match() 가 부서/언어 정렬 후 best 1개 반환
    try:
        from core.scenarios import repository

        db_match = repository.match(query, division=division, lang=lang)
        if db_match:
            return CollaborationScenario(
                id=db_match["scenario_id"],
                trigger_keywords=list(db_match.get("trigger_keywords") or []),
                situation=db_match.get("situation") or "",
                requesting_dept=db_match.get("requesting_dept") or "",
                my_actions=list(db_match.get("my_actions") or []),
                hand_off_to=db_match.get("hand_off_to") or "",
                hand_off_items=list(db_match.get("hand_off_items") or []),
                deadline_info=db_match.get("deadline_info") or "",
                related_sop_id=db_match.get("related_sop_id") or "",
                tips=list(db_match.get("tips") or []),
            )
    except Exception:
        # DB 실패 시 디스크 시드 사용 (안전장치 — repository 가 부재한 단위 테스트 환경 등)
        pass

    # 디스크 시드 매칭
    q_lower = (query or "").lower()
    for scenario in _load_collab_from_disk():
        for kw in scenario.trigger_keywords:
            if kw.lower() in q_lower:
                return scenario
    return None


def format_collaboration_response(scenario: CollaborationScenario) -> str:
    """협업 시나리오를 마크다운 응답 텍스트로 변환"""
    lines = [
        f"### 부서 간 협업 가이드: {scenario.id}",
        "",
        f"**상황:** {scenario.situation}",
        f"**요청 부서:** {scenario.requesting_dept}",
        "",
        "**내가 준비해야 할 것:**",
    ]
    for i, action in enumerate(scenario.my_actions, 1):
        lines.append(f"  {i}. {action}")

    lines.append("")
    lines.append(f"**넘겨야 할 곳:** {scenario.hand_off_to}")
    lines.append("")
    lines.append("**넘겨야 할 산출물:**")
    for item in scenario.hand_off_items:
        lines.append(f"  - {item}")

    lines.append("")
    lines.append(f"**기한:** {scenario.deadline_info}")

    if scenario.related_sop_id:
        lines.append(f"\n> 관련 SOP: `{scenario.related_sop_id}` — 상세 절차는 SOP 가이드에서 확인하세요.")

    if scenario.tips:
        lines.append("\n**신입을 위한 팁:**")
        for tip in scenario.tips:
            lines.append(f"  - {tip}")

    return "\n".join(lines)
