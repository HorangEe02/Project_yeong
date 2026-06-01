"""인원 검색 엔진 — 자연어 질문에서 조건을 추출하여 DB 검색"""

import re
from features.search.employee.database import EmployeeDatabase, POSITION_HIERARCHY

DEPARTMENT_ALIASES = {
    # 안전보건팀
    "안전": "안전보건팀", "보건": "안전보건팀", "안전보건": "안전보건팀",
    "안전팀": "안전보건팀", "보건팀": "안전보건팀",
    # 품질보증팀
    "품질보증": "품질보증팀", "품보": "품질보증팀", "QA": "품질보증팀",
    "품질팀": "품질보증팀", "품보팀": "품질보증팀",
    # 품질경영팀
    "품질경영": "품질경영팀", "품경": "품질경영팀", "QM": "품질경영팀",
    "품경팀": "품질경영팀",
    # 생산관리팀
    "생산관리": "생산관리팀", "생관": "생산관리팀", "생관팀": "생산관리팀",
    # 생산기술팀
    "생산기술": "생산기술팀", "생기": "생산기술팀", "생기팀": "생산기술팀",
    # 총무인사팀
    "총무인사": "총무인사팀", "총무": "총무인사팀", "인사": "총무인사팀",
    "총무팀": "총무인사팀", "인사팀": "총무인사팀", "HR": "총무인사팀",
    # IT전략팀
    "IT": "IT전략팀", "IT전략": "IT전략팀", "전산": "IT전략팀",
    "IT팀": "IT전략팀", "전산팀": "IT전략팀",
    # 구매/해외/상생
    "구매": "구매팀", "해외지원": "해외지원팀", "해외": "해외지원팀",
    "해외팀": "해외지원팀", "상생": "상생협력팀", "상생협력": "상생협력팀",
    # 영업/자재
    "영업": "영업팀", "자재": "자재관리팀", "자재관리": "자재관리팀",
    "자재팀": "자재관리팀",
    # 개발본부
    "기술영업": "기술영업팀", "부품개발": "부품개발팀", "부품": "부품개발팀",
    "부품팀": "부품개발팀",
    "금형": "금형생산팀", "금형생산": "금형생산팀", "금형팀": "금형생산팀",
    # 생산기술본부
    "자동화": "자동화기술팀", "자동화팀": "자동화기술팀",
    "FA": "FA사업팀", "FA팀": "FA사업팀",
    "플랜트": "플랜트사업팀", "플랜트팀": "플랜트사업팀",
    "설계": "제품설계팀", "제품설계": "제품설계팀", "설계팀": "제품설계팀",
    "공법": "공법계획팀", "공법계획": "공법계획팀", "공법팀": "공법계획팀",
    "용기": "용기운영팀", "용기팀": "용기운영팀",
    "비전": "비전연구팀", "비전연구": "비전연구팀", "비전팀": "비전연구팀",
    # 기술연구소
    "바디": "바디선행개발팀", "바디선행": "바디선행개발팀", "바디팀": "바디선행개발팀",
    "전장": "전장선행개발팀", "전장선행": "전장선행개발팀", "전장팀": "전장선행개발팀",
    # 관리본부
    "ESG": "ESG경영팀", "ESG팀": "ESG경영팀",
    "교육": "기술교육원", "기술교육": "기술교육원", "교육원": "기술교육원",
    # 독립
    "감사": "내부감사팀", "내부감사": "내부감사팀", "감사팀": "내부감사팀",
    # 재경본부
    "재무": "재무팀", "회계": "회계팀", "원가": "원가기획팀", "원가팀": "원가기획팀",
}

DIVISION_ALIASES = {
    "재경": "재경본부", "관리": "관리본부", "구매": "구매본부",
    "생산": "생산본부", "개발": "개발본부", "생산기술": "생산기술본부",
    "연구소": "기술연구소", "기술연구": "기술연구소",
}

# "생산" 같은 애매한 키워드 → 본부 단위 검색으로 전환
_AMBIGUOUS_TO_DIVISION = {
    "생산": "생산본부",
}

_EXCLUDED_NAMES = (
    set(DEPARTMENT_ALIASES.keys()) | set(DIVISION_ALIASES.keys()) | set(POSITION_HIERARCHY.keys())
    | {"연락처", "이메일", "전화", "내선", "팀장", "팀원", "사람",
       "인원", "현황", "조직도", "부서", "알려", "찾아", "누구",
       "담당자", "책임자", "조회", "검색", "경산", "경주", "본사", "공장",
       "사람", "사람들", "소속", "전체", "목록", "리스트", "보여",
       "인원들", "인원들을", "직원들", "팀원들", "알려", "알려줘", "보여줘",
       "부서원", "부서원들", "구성원", "멤버",
       "이메일을", "연락처를", "전화를", "번호를", "내선을",
       "전화번호", "이메일", "연락처", "내선번호",
       "전번", "메일", "출력", "결과", "정보", "데이터",
       "전략팀", "생산팀", "관리팀", "보증팀", "보건팀",
       "개발팀", "운영팀", "기획팀", "교육원", "연구팀",
       "사업팀", "영업팀", "설계팀", "계획팀", "협력팀", "지원팀"}
)


class EmployeeSearchEngine:
    """자연어 질문에서 인원을 검색한다."""

    def __init__(self, db: EmployeeDatabase):
        self.db = db

    def search(self, query: str) -> dict:
        parsed = self._parse_query(query.strip())

        if parsed.get("org_chart"):
            return self._handle_org_chart(parsed)
        if parsed.get("stats") and not parsed.get("position"):
            return self._handle_stats(parsed)
        # 부분 매칭 키워드 (예: "기술" → 생산기술팀, 자동화기술팀, 기술영업팀, 기술교육원)
        if parsed.get("_partial_keyword") and not parsed.get("name"):
            return self._handle_partial_keyword(parsed)
        # 부서 + 직급 조합 (예: "품질보증팀 대리")
        if parsed.get("department") and parsed.get("position") and not parsed.get("name"):
            return self._handle_department_with_position(parsed)
        # 본부 + 직급 (예: "생산 부장" → 생산본부 전체에서 부장 검색)
        if parsed.get("division") and parsed.get("position") and not parsed.get("name"):
            return self._handle_division_with_position(parsed)
        if parsed.get("department") and not parsed.get("name"):
            return self._handle_department(parsed)
        if parsed.get("division") and not parsed.get("name"):
            return self._handle_stats(parsed)
        return self._handle_person(parsed)

    def _parse_query(self, query: str) -> dict:
        parsed = {
            "name": None, "department": None, "division": None,
            "position": None, "plant": None, "extension": None,
            "team_leader_only": False, "org_chart": False, "stats": False,
            "raw_query": query,
        }

        if any(kw in query for kw in ["조직도", "조직 구조", "조직 현황"]):
            parsed["org_chart"] = True
            return parsed

        if any(kw in query for kw in ["인원 현황", "인원현황", "몇 명", "몇명", "인원 수", "인원수"]):
            parsed["stats"] = True

        # "~팀 사람들" / "~팀 전체" 패턴 → 부서 조회로 강제
        if any(kw in query for kw in ["사람들", "사람", "전체", "목록", "리스트", "소속"]):
            parsed["stats"] = True

        if any(kw in query for kw in ["팀장", "책임자", "담당자"]):
            parsed["team_leader_only"] = True

        # v3.6 — 명시적 "X본부" 패턴은 부서 매칭보다 우선 처리.
        # "생산기술본부" 가 DEPARTMENT_ALIASES 의 "생산기술" 부분 매칭으로
        # 부서(생산기술팀) 으로 잘못 인식되는 버그 수정.
        if "본부" in query:
            # alias 길이 긴 것 우선 (생산기술 > 생산 — 부분 매칭 우선순위)
            for alias, full in sorted(DIVISION_ALIASES.items(), key=lambda x: -len(x[0])):
                if alias in query:
                    parsed["division"] = full
                    break
            # alias 매핑 없으면 full 본부명 직접 매칭 ("기술연구소" 등)
            if not parsed["division"]:
                for full in sorted(set(DIVISION_ALIASES.values()), key=len, reverse=True):
                    if full in query:
                        parsed["division"] = full
                        break
            # 본부 매칭 성공 시 부서/사람 이름 추출 스킵 — 직급/공장만 추가
            if parsed["division"]:
                for pos in POSITION_HIERARCHY:
                    if pos in query or f"{pos}님" in query:
                        parsed["position"] = pos
                        break
                plant_map = {"경산": "경산 본사", "제2공장": "경산 제2공장",
                             "경주": "경주 구어공장", "구어": "경주 구어공장"}
                for alias, plant in plant_map.items():
                    if alias in query:
                        parsed["plant"] = plant
                        break
                # 본부+직급 조합은 명확한 목록 조회 — stats 플래그 무력화
                parsed["stats"] = False
                return parsed

        # 부서명 추출 — 조사 제거 후 매칭 ("금형에" → "금형", "부품의" → "부품")
        _particles = ["에서", "에게", "한테", "의", "에", "은", "는", "이", "가", "을", "를", "도", "로"]
        for alias, full in sorted(DEPARTMENT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            if alias in query:
                parsed["department"] = full
                break
        # 직접 매칭 실패 시, 쿼리 내 각 어절에서 조사를 제거하고 재매칭
        if not parsed["department"]:
            for word in query.split():
                stem = word
                for p in sorted(_particles, key=len, reverse=True):
                    if stem.endswith(p) and len(stem) > len(p):
                        stem = stem[:-len(p)]
                        break
                if stem in DEPARTMENT_ALIASES:
                    parsed["department"] = DEPARTMENT_ALIASES[stem]
                    break

        # 여전히 실패 시: 부서명에 키워드가 포함된 부서를 부분 매칭
        if not parsed["department"] and not parsed["division"]:
            _all_depts = set(DEPARTMENT_ALIASES.values())
            for word in query.split():
                stem = word
                for p in sorted(_particles, key=len, reverse=True):
                    if stem.endswith(p) and len(stem) > len(p):
                        stem = stem[:-len(p)]
                        break
                if len(stem) >= 2 and stem not in POSITION_HIERARCHY:
                    matches = [d for d in _all_depts if stem in d]
                    if len(matches) == 1:
                        parsed["department"] = matches[0]
                        break
                    elif len(matches) > 1:
                        # 여러 부서 매칭 → _partial_dept_keyword로 저장
                        parsed["_partial_keyword"] = stem
                        break

        if not parsed["department"]:
            for alias, full in DIVISION_ALIASES.items():
                if alias in query and "본부" in query:
                    parsed["division"] = full
                    break
            # "생산 부장" 처럼 애매한 경우 본부 단위로 검색
            if not parsed["division"]:
                for word in query.split():
                    stem = word
                    for p in _particles:
                        if stem.endswith(p) and len(stem) > len(p):
                            stem = stem[:-len(p)]
                            break
                    if stem in _AMBIGUOUS_TO_DIVISION:
                        parsed["division"] = _AMBIGUOUS_TO_DIVISION[stem]
                        break

        for pos in POSITION_HIERARCHY:
            # "대리님", "과장님" 등 "님" 접미사도 매칭
            if pos in query or f"{pos}님" in query:
                parsed["position"] = pos
                break

        plant_map = {"경산": "경산 본사", "제2공장": "경산 제2공장",
                     "경주": "경주 구어공장", "구어": "경주 구어공장"}
        for alias, plant in plant_map.items():
            if alias in query:
                parsed["plant"] = plant
                break

        ext_match = re.search(r'(\d{4})', query)
        if ext_match and any(kw in query for kw in ["내선", "번호"]):
            parsed["extension"] = ext_match.group(1)

        name_candidates = re.findall(r'[가-힣]{2,4}', query)
        # 이미 파싱된 부서명/본부명은 이름 후보에서 제외
        _dynamic_exclude = set()
        if parsed["department"]:
            dept_name = parsed["department"]
            _dynamic_exclude.add(dept_name)
            # "영업팀" → "영업", "금형생산팀" → "금형생산" 등
            if dept_name.endswith("팀"):
                _dynamic_exclude.add(dept_name[:-1])
            if dept_name.endswith("원"):
                _dynamic_exclude.add(dept_name[:-1])
            for alias, full in DEPARTMENT_ALIASES.items():
                if full == dept_name:
                    _dynamic_exclude.add(alias)
        if parsed["division"]:
            _dynamic_exclude.add(parsed["division"])
        if parsed.get("_partial_keyword"):
            _dynamic_exclude.add(parsed["_partial_keyword"])

        _suffix_patterns = {"들을", "에게", "한테", "해줘", "줘요", "인원", "부서",
                            "일을", "메일", "메일을", "락처", "락처를", "화를", "선을", "호를"}
        # 직급+"님" 패턴도 제외 (대리님, 과장님 등)
        _pos_nim = {f"{p}님" for p in POSITION_HIERARCHY}
        for cand in name_candidates:
            if cand in _EXCLUDED_NAMES or cand in _dynamic_exclude or cand in _pos_nim:
                continue
            if any(cand.endswith(s) for s in _suffix_patterns):
                continue
            # "~을/를/의/에/도/는/서/님/팀" 으로 끝나는 3자 이상은 이름이 아님
            if len(cand) >= 3 and cand[-1] in "을를의에도는서님팀":
                continue
            if len(cand) <= 4:
                parsed["name"] = cand
                break

        return parsed

    def _handle_person(self, parsed: dict) -> dict:
        results = []
        if parsed.get("extension"):
            results = self.db.search_by_extension(parsed["extension"])
        elif parsed.get("name"):
            if parsed.get("team_leader_only") and parsed.get("department"):
                leader = self.db.get_team_leader(parsed["department"])
                results = [leader] if leader else []
            else:
                results = self.db.search(
                    name=parsed["name"], department=parsed.get("department"),
                    position=parsed.get("position"),
                )
        elif parsed.get("department") and parsed.get("team_leader_only"):
            leader = self.db.get_team_leader(parsed["department"])
            results = [leader] if leader else []
        else:
            results = self.db.search(
                department=parsed.get("department"), position=parsed.get("position"),
                plant=parsed.get("plant"),
            )

        message = ""
        if not results:
            message = "검색 결과가 없습니다. 이름이나 부서명을 다시 확인해주세요."
        elif len(results) > 10:
            message = f"총 {len(results)}명이 검색되었습니다. 이름, 부서, 직급으로 범위를 좁혀주세요."

        return {"mode": "person", "results": results, "message": message, "query_parsed": parsed}

    def _handle_partial_keyword(self, parsed: dict) -> dict:
        """부분 키워드 매칭 — 여러 부서에 걸치는 검색 (예: "기술" → 기술 포함 모든 부서)"""
        keyword = parsed["_partial_keyword"]
        position = parsed.get("position")
        _all_depts = set(DEPARTMENT_ALIASES.values())
        matched_depts = [d for d in _all_depts if keyword in d]

        all_results = []
        for dept in sorted(matched_depts):
            if position:
                members = self.db.search(department=dept, position=position)
            else:
                members = self.db.get_department_members(dept)
            all_results.extend(members)

        pos_str = f" {position}" if position else ""
        dept_str = " / ".join(sorted(matched_depts))
        return {
            "mode": "person" if position else "department",
            "results": all_results,
            "message": f"\"{keyword}\" 포함 부서{pos_str}: {dept_str} (총 {len(all_results)}명)",
            "query_parsed": parsed,
        }

    def _handle_division_with_position(self, parsed: dict) -> dict:
        """본부 + 직급 조합 조회 (예: 생산 부장 → 생산본부 전체에서 부장 검색)"""
        division = parsed.get("division")
        position = parsed.get("position")
        results = self.db.search(division=division, position=position)
        label = f"{division} {position}" if position else division
        return {
            "mode": "person",
            "results": results,
            "message": f"{label}: 총 {len(results)}명",
            "query_parsed": parsed,
        }

    def _handle_department_with_position(self, parsed: dict) -> dict:
        """부서 + 직급 조합 조회 (예: 품질보증팀 대리)"""
        dept = parsed.get("department")
        position = parsed.get("position")
        results = self.db.search(department=dept, position=position)
        pos_label = f"{dept} {position}" if position else dept
        return {
            "mode": "person",
            "results": results,
            "message": f"{pos_label}: 총 {len(results)}명",
            "query_parsed": parsed,
        }

    def _handle_department(self, parsed: dict) -> dict:
        dept = parsed.get("department")
        if parsed.get("stats"):
            if dept:
                members = self.db.get_department_members(dept)
                return {"mode": "department", "results": members,
                        "message": f"{dept}: 총 {len(members)}명", "query_parsed": parsed}
            headcount = self.db.get_department_headcount()
            return {"mode": "stats", "results": headcount,
                    "message": f"전체 {self.db.get_total_headcount()}명", "query_parsed": parsed}
        members = self.db.get_department_members(dept)
        return {"mode": "department", "results": members,
                "message": f"{dept}: 총 {len(members)}명", "query_parsed": parsed}

    def _handle_org_chart(self, parsed: dict) -> dict:
        org_tree = self.db.get_org_tree()
        return {"mode": "org_chart", "results": org_tree,
                "message": f"전체 {self.db.get_total_headcount()}명", "query_parsed": parsed}

    def _handle_stats(self, parsed: dict) -> dict:
        dept = parsed.get("department")
        division = parsed.get("division")
        if dept:
            members = self.db.get_department_members(dept)
            return {"mode": "department", "results": members,
                    "message": f"{dept}: 총 {len(members)}명", "query_parsed": parsed}
        if division:
            members = self.db.get_division_members(division)
            return {"mode": "stats", "results": members,
                    "message": f"{division}: 총 {len(members)}명", "query_parsed": parsed}
        headcount = self.db.get_department_headcount()
        return {"mode": "stats", "results": headcount,
                "message": f"전체 {self.db.get_total_headcount()}명", "query_parsed": parsed}
