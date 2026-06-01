"""v3.3 Phase 0-3 / Phase D — Quick Questions 데이터 풀 검증.

검증 대상:
1. 35 파일 / 199 질문 / ID 유니크성 (Turn 1~5 누적 결과)
2. 박부장형 인물 지칭 0건 (정규식: 한국인 성씨 80자 + 직급 6종)
3. 필수 필드 (id, label, promptText, category, min_level, max_level)
4. category ∈ {scenario, action, sop, general}
5. min_level ≤ max_level, 둘 다 1~5
6. promptText 길이 5~80 (UX 적합성)
7. 8 본부(+_meta) 모두 데이터 보유
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

QQ_DIR = PROJECT_ROOT / "data" / "knowledge_base" / "quick_questions"

# 한국인 대표 성씨 80개 (인구 기준 상위)
KOREAN_SURNAMES = (
    "김이박최정강조윤장임한오서신권황안송류홍"
    "전고문손양배백허노남심구차주우진민원천방"
    "함현표명기반왕금옥인맹제모도소선설육진"
    "길연위염여추마지엄채용예부피변"
)
PERSONAL = re.compile(rf"[{KOREAN_SURNAMES}][가-힣]{{1,2}}\s*(?:부장|차장|과장|전무|상무|이사)\b")

REQUIRED_FIELDS = ("id", "label", "promptText", "category", "min_level", "max_level")
VALID_CATEGORIES = {"scenario", "action", "sop", "general"}


def _all_files() -> list[Path]:
    return sorted(QQ_DIR.rglob("*.json"))


def _all_questions() -> list[tuple[str, dict]]:
    """[(filename, question_dict), ...] 평면화."""
    out: list[tuple[str, dict]] = []
    for f in _all_files():
        data = json.loads(f.read_text(encoding="utf-8"))
        for q in data.get("questions", []):
            out.append((f.name, q))
    return out


# ──────────────────────────────────────────────
# 1. 데이터 존재 + 카운트
# ──────────────────────────────────────────────


def test_qq_directory_exists():
    assert QQ_DIR.exists(), f"{QQ_DIR} 가 존재하지 않습니다."
    assert (QQ_DIR / "_common.json").exists()
    assert (QQ_DIR / "_by_level").is_dir()


def test_qq_total_files_at_least_35():
    """Turn 1~5 누적 — 5 메타 + 30 부서 = 35 이상."""
    files = _all_files()
    assert len(files) >= 35, f"파일 수 부족: {len(files)}"


def test_qq_total_questions_at_least_180():
    """약 180+ 큐레이션 목표 (실제 199)."""
    qs = _all_questions()
    assert len(qs) >= 180, f"질문 수 부족: {len(qs)}"


# ──────────────────────────────────────────────
# 2. JSON 구조 + 필수 필드
# ──────────────────────────────────────────────


def test_qq_all_files_parse():
    """모든 JSON 이 파싱 가능해야 한다."""
    for f in _all_files():
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise AssertionError(f"{f.name} :: 파싱 실패 — {e}") from e


def test_qq_required_fields_present():
    for fname, q in _all_questions():
        for field in REQUIRED_FIELDS:
            assert field in q, f"{fname} :: {q.get('id', '?')} — 필수 필드 누락 [{field}]"


def test_qq_valid_categories():
    for fname, q in _all_questions():
        assert q["category"] in VALID_CATEGORIES, (
            f"{fname} :: {q['id']} — 잘못된 category [{q['category']}]"
        )


def test_qq_level_range():
    for fname, q in _all_questions():
        mn, mx = q["min_level"], q["max_level"]
        assert isinstance(mn, int) and 1 <= mn <= 5, f"{fname} :: {q['id']} — min_level={mn}"
        assert isinstance(mx, int) and 1 <= mx <= 5, f"{fname} :: {q['id']} — max_level={mx}"
        assert mn <= mx, f"{fname} :: {q['id']} — min({mn}) > max({mx})"


def test_qq_prompt_length():
    """UX 적합성 — promptText 5~80 자."""
    for fname, q in _all_questions():
        n = len(q["promptText"])
        assert 5 <= n <= 80, f"{fname} :: {q['id']} — promptText 길이 {n} (5~80)"


# ──────────────────────────────────────────────
# 3. ID 유니크
# ──────────────────────────────────────────────


def test_qq_ids_unique():
    seen: dict[str, str] = {}
    for fname, q in _all_questions():
        qid = q["id"]
        assert qid not in seen, (
            f"중복 ID [{qid}] — {seen[qid]} 와 {fname} 양쪽에서 발견"
        )
        seen[qid] = fname


# ──────────────────────────────────────────────
# 4. 박부장형 인물 지칭 0건
# ──────────────────────────────────────────────


def test_qq_no_personal_names():
    """한국인 성씨 + 1~2자 이름 + 직급 패턴이 0건이어야 한다."""
    hits = []
    for fname, q in _all_questions():
        m = PERSONAL.search(q["promptText"])
        if m:
            hits.append(f"{fname} :: {q['id']} — '{m.group()}' in '{q['promptText']}'")
    assert not hits, "박부장형 검출:\n  " + "\n  ".join(hits)


# ──────────────────────────────────────────────
# 5. 본부 커버리지
# ──────────────────────────────────────────────


def test_qq_division_coverage():
    """8 본부(+_meta) 모두 데이터 보유."""
    EXPECTED_DIVISIONS = {
        "생산본부",
        "생산기술본부",
        "개발본부",
        "기술연구소",
        "관리본부",
        "구매본부",
        "재경본부",
        "(독립)",
    }
    seen_divs: set[str] = set()
    for f in _all_files():
        data = json.loads(f.read_text(encoding="utf-8"))
        div = data.get("division")
        if div:
            seen_divs.add(div)
    missing = EXPECTED_DIVISIONS - seen_divs
    assert not missing, f"누락 본부: {missing}"


def test_qq_meta_files_exist():
    """공통 + 5 직급 메타 파일 존재."""
    assert (QQ_DIR / "_common.json").exists()
    for lvl in ("L1", "L2", "L3", "L4_5"):
        assert (QQ_DIR / "_by_level" / f"{lvl}.json").exists(), f"누락: {lvl}.json"


# ──────────────────────────────────────────────
# 6. 카테고리 분포 — action 비중이 가장 높아야 (행동 유도 챗봇)
# ──────────────────────────────────────────────


def test_qq_action_is_dominant_category():
    from collections import Counter

    cnt: Counter[str] = Counter()
    for _, q in _all_questions():
        cnt[q["category"]] += 1
    most_common = cnt.most_common(1)[0][0]
    assert most_common == "action", (
        f"카테고리 분포 부적합 — 1위: {most_common}, action 이어야 함. 분포: {dict(cnt)}"
    )
