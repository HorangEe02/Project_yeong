"""1회용 추출 스크립트 — Feature C Sprint 1 P0 (plan §27.3 Day 1).

기존 sop_guide.SOP_DATABASE / collaboration_guide.COLLABORATION_SCENARIOS 의
hardcoded dataclass 인스턴스를 dict → JSON 으로 직렬화.

citation_id 규칙 (plan §35 Q3 → 단순 형식 채택):
  - SOP: sop_id 그대로 (예: "SOP-001")
  - Collaboration: scenario_id 그대로 (예: "COLLAB-quality-sales")

사용:
    python scripts/extract_sop_to_json.py

idempotent — 같은 파일을 여러 번 실행해도 동일 결과.
스크립트 1회 실행 후 sop_guide.py / collaboration_guide.py 가 디스크 로더로 교체되면
이 스크립트는 archive (삭제하지 않음 — Sprint 5 contents 확장 시 재사용).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DATA_DIR = REPO_ROOT / "data" / "knowledge_base"
SOPS_DIR = DATA_DIR / "sops"
COLLAB_DIR = DATA_DIR / "collaboration"


def extract_sops() -> int:
    """sop_guide.SOP_DATABASE → data/knowledge_base/sops/*.json"""
    from features.onboarding.sop_guide import SOP_DATABASE

    SOPS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for sop_id, doc in SOP_DATABASE.items():
        payload = asdict(doc)
        # citation_id 부여 (Sprint 2 citation_enforcer 의 키)
        payload["citation_id"] = sop_id
        out_path = SOPS_DIR / f"{sop_id}.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written += 1
        print(f"  ✓ {out_path.relative_to(REPO_ROOT)}")
    return written


def extract_collaboration() -> int:
    """collaboration_guide.COLLABORATION_SCENARIOS (list of dataclass)
    → data/knowledge_base/collaboration/*.json. 각 dataclass 의 `id` 가 파일명."""
    try:
        from features.onboarding.collaboration_guide import COLLABORATION_SCENARIOS
    except ImportError as e:
        print(f"  ! collaboration_guide import 실패: {e}")
        return 0

    COLLAB_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for doc in COLLABORATION_SCENARIOS:
        scenario_id = getattr(doc, "id", "") or ""
        if not scenario_id:
            print("  ! 시나리오 id 누락 — skip")
            continue
        payload = asdict(doc)
        payload["citation_id"] = scenario_id
        out_path = COLLAB_DIR / f"{scenario_id}.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written += 1
        print(f"  ✓ {out_path.relative_to(REPO_ROOT)}")
    return written


def extract_glossary_aliases() -> int:
    """glossary_matcher.TERM_ALIASES → data/knowledge_base/glossary_aliases/aliases.json"""
    try:
        from features.onboarding.glossary_matcher import TERM_ALIASES
    except ImportError as e:
        print(f"  ! glossary_matcher import 실패: {e}")
        return 0

    out_dir = DATA_DIR / "glossary_aliases"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "aliases.json"
    out_path.write_text(
        json.dumps(dict(TERM_ALIASES), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"  ✓ {out_path.relative_to(REPO_ROOT)} ({len(TERM_ALIASES)} aliases)")
    return len(TERM_ALIASES)


def main() -> int:
    print("── SOP 추출 ──────────────────────────")
    n_sop = extract_sops()
    print(f"  → {n_sop} SOP JSON 생성\n")

    print("── 협업 시나리오 추출 ────────────────")
    n_collab = extract_collaboration()
    print(f"  → {n_collab} 협업 JSON 생성\n")

    print("── glossary aliases 추출 ─────────────")
    n_alias = extract_glossary_aliases()
    print(f"  → {n_alias} 별칭 JSON 생성\n")

    print("=== 추출 완료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
