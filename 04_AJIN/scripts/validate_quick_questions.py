"""v3.3 Feature C — Quick Questions 검증 스크립트 (Phase 0-3).

검증 항목:
1. JSON 파싱 성공
2. 필수 필드 (id, label, promptText, category, min_level, max_level)
3. ID 전역 유니크
4. category ∈ {scenario, action, sop, general}
5. min_level ≤ max_level, 둘 다 1~5
6. **박부장형 인물 지칭 금지** — 한국인 성씨(80개) + 이름(1~2자) + 직급(부장/차장/과장/전무/상무/이사) 패턴
   * "신입사원", "정규대리"같은 일반 명사 합성어는 false positive — 사원/대리/책임/팀장은 직급 키워드에서 제외
7. promptText 길이 5~80자 (UX 적합성)

사용:
    python scripts/validate_quick_questions.py
    # exit 0 = 통과, exit 1 = 이슈 있음
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QQ_DIR = ROOT / "data" / "knowledge_base" / "quick_questions"

# 한국인 대표 성씨 80개 (인구 기준 상위)
KOREAN_SURNAMES = (
    "김이박최정강조윤장임한오서신권황안송류홍"
    "전고문손양배백허노남심구차주우진민원천방"
    "함현현표명기반왕금옥인맹제모도소선설육진"
    "길연위염여추마지엄채용함예부피변"
)
SURNAME_CLASS = f"[{KOREAN_SURNAMES}]"

# 직급 — 일반 명사 합성어가 많은 사원/대리/책임/팀장은 제외
TITLES = ("부장", "차장", "과장", "전무", "상무", "이사")
TITLE_CLASS = "(?:" + "|".join(TITLES) + ")"

# 박부장 / 김민수차장 / 이수부장 — 성씨(1) + 이름(1~2) + 직급
PERSONAL = re.compile(rf"{SURNAME_CLASS}[가-힣]{{1,2}}\s*{TITLE_CLASS}\b")

REQUIRED_FIELDS = ("id", "label", "promptText", "category", "min_level", "max_level")
VALID_CATEGORIES = {"scenario", "action", "sop", "general"}


def validate() -> int:
    issues: list[str] = []
    ids_seen: dict[str, str] = {}
    by_div: Counter[str] = Counter()
    by_cat: Counter[str] = Counter()
    total_q = 0
    total_files = 0

    if not QQ_DIR.exists():
        print(f"[FAIL] {QQ_DIR} 가 존재하지 않습니다.")
        return 1

    for f in sorted(QQ_DIR.rglob("*.json")):
        total_files += 1
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            issues.append(f"{f.name} :: JSON 파싱 실패 — {e}")
            continue

        div = data.get("division", "_meta")
        for q in data.get("questions", []):
            total_q += 1
            qid = q.get("id", "?")

            # 필수 필드
            for k in REQUIRED_FIELDS:
                if k not in q:
                    issues.append(f"{f.name} :: {qid} — 필수 필드 누락 [{k}]")

            # 중복 ID
            if qid in ids_seen:
                issues.append(f"{f.name} :: 중복 ID [{qid}] — 이전: {ids_seen[qid]}")
            ids_seen[qid] = f.name

            # category
            cat = q.get("category", "")
            if cat not in VALID_CATEGORIES:
                issues.append(f"{f.name} :: {qid} — 잘못된 category [{cat}]")
            by_cat[cat] += 1
            by_div[div] += 1

            # level
            mn, mx = q.get("min_level"), q.get("max_level")
            if not (isinstance(mn, int) and 1 <= mn <= 5):
                issues.append(f"{f.name} :: {qid} — min_level 범위 [{mn}]")
            if not (isinstance(mx, int) and 1 <= mx <= 5):
                issues.append(f"{f.name} :: {qid} — max_level 범위 [{mx}]")
            if isinstance(mn, int) and isinstance(mx, int) and mn > mx:
                issues.append(f"{f.name} :: {qid} — min > max [{mn}>{mx}]")

            # promptText 길이
            pt = q.get("promptText", "")
            if not (5 <= len(pt) <= 80):
                issues.append(f"{f.name} :: {qid} — promptText 길이 {len(pt)} (5~80 권장)")

            # 박부장형
            m = PERSONAL.search(pt)
            if m:
                issues.append(f"{f.name} :: {qid} — 박부장형 검출 [{m.group()}] in '{pt}'")

    print(f"[FILES] {total_files}")
    print(f"[QUESTIONS] {total_q}")
    print(f"[UNIQUE IDS] {len(ids_seen)}")
    print(f"[BY DIVISION]")
    for d, n in by_div.most_common():
        print(f"  {d}: {n}")
    print(f"[BY CATEGORY] action={by_cat['action']} sop={by_cat['sop']} scenario={by_cat['scenario']} general={by_cat['general']}")

    if issues:
        print(f"\n[ISSUES] {len(issues)}건:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("\n[PASS] 모든 검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
