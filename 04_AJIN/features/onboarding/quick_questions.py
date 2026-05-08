"""v3.3 Phase D — Quick Questions 개인화 모듈.

데이터 풀: ``data/knowledge_base/quick_questions/`` (Phase 0-3 에서 큐레이션 — 35 파일 / 199 질문)
- ``_common.json`` — 부서·직급 무관 공통 (3개)
- ``_by_level/L1.json`` ~ ``L4_5.json`` — 직급별 (4~5 슬롯)
- ``{department}.json`` × 30 — 부서별 (4~6 질문)

노출 알고리즘 (총 6개 슬롯):
1. _common.json 3개
2. _by_level/L{role_level}.json 의 상위 2개
3. {department}.json 의 상위 4개
4. (옵션) team JSON 의 상위 1개 (현재 미구현, 향후 확장 가능)
5. ID 중복 제거 + 박부장형 정규식 차단 (안전망)
6. 6개로 트림

박부장형 차단 정규식: 한국인 성씨 80자 + 직급 6종 (rbac.ts 와 정합)
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
QQ_DIR = PROJECT_ROOT / "data" / "knowledge_base" / "quick_questions"
TARGET_SLOT_COUNT = 6  # 한 줄 칩 6개 디자인 한도

# 박부장형 안전망 (test_phase_a_quick_questions.py 와 동일 정규식)
_KOREAN_SURNAMES = (
    "김이박최정강조윤장임한오서신권황안송류홍"
    "전고문손양배백허노남심구차주우진민원천방"
    "함현표명기반왕금옥인맹제모도소선설육진"
    "길연위염여추마지엄채용예부피변"
)
# Korean 단어 경계는 \b 만으로 부족 — '과장님' 같은 후행 한글 문자도 차단해야 함.
# 음성 lookahead 로 직급 뒤에 한글이 안 오는 경우만 매칭 (단, '님' 1글자는 예외).
_PERSONAL_PATTERN = re.compile(
    rf"[{_KOREAN_SURNAMES}][가-힣]{{1,2}}\s*(?:부장|차장|과장|전무|상무|이사)(?:님)?(?![가-힣])"
)


def _has_personal_name(text: str) -> bool:
    """박부장형 인물 지칭 여부 (안전망 — 데이터에는 이미 0건)."""
    return bool(_PERSONAL_PATTERN.search(text or ""))


def _generate_fallback_questions(department: str, take: int = 4) -> list[dict]:
    """v3.3 Phase D-3 — 부서 JSON 누락/부족 시 자동 보충 생성.

    DEPARTMENT_PROFILES 의 ``core_responsibilities`` 를 시드로 사용해
    ``"{책임} 관련 절차 알려줘"`` 형태의 질문을 생성한다.

    데이터 풀에 신설 부서가 추가될 때까지의 임시 fallback 역할.
    """
    try:
        from features.onboarding.department_router import DEPARTMENT_PROFILES
    except ImportError:
        return []

    profile = DEPARTMENT_PROFILES.get(department)
    if not profile or not profile.core_responsibilities:
        return []

    questions: list[dict] = []
    for i, resp in enumerate(profile.core_responsibilities[:take]):
        # 첫 키워드 (콤마 이전) 만 라벨로 사용 — UX 가독성
        label_short = resp.split(",")[0].split("·")[0].strip()[:14]
        prompt = f"{resp.split(',')[0].strip()} 관련 절차 알려줘"

        # 박부장형 안전망 (책임 텍스트에는 인물 지칭이 없을 가능성 높지만 방어)
        if _has_personal_name(prompt):
            continue

        questions.append({
            "id": f"auto-{department}-{i}",
            "label": label_short,
            "promptText": prompt,
            "category": "general",
            "min_level": 1,
            "max_level": 5,
            "tags": ["자동생성", "fallback"],
        })
    return questions


@lru_cache(maxsize=1)
def _load_all() -> dict:
    """전체 JSON 데이터를 모듈 캐시로 1회 로드.

    Returns:
        {
            "common": [...],                 # 3개
            "by_level": {1: [...], 2: [...], 3: [...], 4: [...], 5: [...]},
            "by_dept": {"품질보증팀": [...], ...},
        }
    """
    result: dict = {"common": [], "by_level": {}, "by_dept": {}}

    if not QQ_DIR.exists():
        logger.warning("Quick Questions 디렉토리 부재: %s", QQ_DIR)
        return result

    # 공통
    common_path = QQ_DIR / "_common.json"
    if common_path.exists():
        result["common"] = json.loads(common_path.read_text(encoding="utf-8")).get("questions", [])

    # 직급별 — L4 와 L5 는 동일 파일 (L4_5.json)
    level_dir = QQ_DIR / "_by_level"
    if level_dir.exists():
        l4_5_qs: list[dict] = []
        l4_5_path = level_dir / "L4_5.json"
        if l4_5_path.exists():
            l4_5_qs = json.loads(l4_5_path.read_text(encoding="utf-8")).get("questions", [])

        for lvl in range(1, 6):
            if lvl >= 4:
                result["by_level"][lvl] = l4_5_qs
                continue
            path = level_dir / f"L{lvl}.json"
            if path.exists():
                result["by_level"][lvl] = json.loads(
                    path.read_text(encoding="utf-8")
                ).get("questions", [])
            else:
                result["by_level"][lvl] = []

    # 부서별 — 언더스코어로 시작하는 파일은 메타이므로 제외
    for path in QQ_DIR.glob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            dept = data.get("department")
            if dept:
                result["by_dept"][dept] = data.get("questions", [])
        except json.JSONDecodeError as e:
            logger.error("Quick Questions JSON 파싱 실패 — %s: %s", path.name, e)

    logger.info(
        "Quick Questions 로드 완료 — common=%d, levels=%d, depts=%d",
        len(result["common"]),
        len(result["by_level"]),
        len(result["by_dept"]),
    )
    return result


def get_quick_questions(
    department: str,
    role_level: int,
    position: str | None = None,
    team: str | None = None,
) -> list[dict]:
    """부서/직급/팀에 맞는 Quick Questions 6개를 반환한다.

    Args:
        department: 부서명 (DEPARTMENT_PROFILES 키와 정합)
        role_level: 1~5 (rbac.ts 와 정합)
        position: 직책 (현재 미사용, 향후 직책별 분기 확장 여지)
        team: 팀명 (현재 미사용, 향후 팀별 추가 슬롯)

    Returns:
        [{id, label, promptText, category, min_level, max_level, tags}, ...]
        최대 ``TARGET_SLOT_COUNT`` 개. 데이터 부재 시 빈 리스트.
    """
    # role_level 을 1~5 범위로 클램프 (비인증 0 → 1, 비정상 99 → 5).
    # 직급별 슬롯 lookup 과 per-question min/max 필터 모두 클램프된 값을 사용해야
    # 일관성이 유지된다 (테스트 회귀 방지).
    level_clamped = max(1, min(5, role_level))

    data = _load_all()
    out: list[dict] = []
    seen: set[str] = set()

    def _push(items: list[dict], take: int) -> None:
        added = 0
        for q in items:
            if added >= take:
                return
            qid = q.get("id")
            if not qid or qid in seen:
                continue
            # 안전망 — 박부장형은 데이터에서 이미 제거됐지만 추가 방어
            if _has_personal_name(q.get("promptText", "")):
                logger.warning("박부장형 차단: %s — %s", qid, q.get("promptText"))
                continue
            # 직급 범위 체크 — clamped 값으로 일관성 유지
            mn = q.get("min_level", 1)
            mx = q.get("max_level", 5)
            if not (mn <= level_clamped <= mx):
                continue
            seen.add(qid)
            out.append(q)
            added += 1

    # 1) 공통 3개
    _push(data["common"], take=3)

    # 2) 직급별 2개
    _push(data["by_level"].get(level_clamped, []), take=2)

    # 3) 부서별 4개
    dept_questions = data["by_dept"].get(department, [])
    before_dept = len(out)
    _push(dept_questions, take=4)
    dept_added = len(out) - before_dept

    # v3.3 Phase D-3 — 부서별 슬롯이 부족하면 DEPARTMENT_PROFILES 기반 fallback 보충
    # 데이터 풀에 미등록 부서이거나 직급 범위로 필터링되어 부족할 때 작동.
    shortage = 4 - dept_added
    if shortage > 0:
        fallback = _generate_fallback_questions(department, take=shortage)
        if fallback:
            logger.info(
                "Quick Questions fallback 적용 — dept=%s 부족=%d 보충=%d",
                department, shortage, len(fallback),
            )
            _push(fallback, take=shortage)

    # 4) 팀별 1개 (옵션 — 현재 데이터 없음)
    # team 인자는 향후 data/knowledge_base/quick_questions/_team/{team}.json 추가 시 활용

    # 6 슬롯 제한
    return out[:TARGET_SLOT_COUNT]


def invalidate_cache() -> None:
    """admin 의 부서 변경 또는 데이터 갱신 후 캐시 무효화."""
    _load_all.cache_clear()
