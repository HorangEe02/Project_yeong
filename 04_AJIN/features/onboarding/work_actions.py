"""
업무 모드 액션 라우터
- 사용자 의도에 따라 다른 Feature 기능을 채팅 내에서 실행
- 결과를 채팅 메시지로 포매팅

v3.3 Phase E — 다중 매칭 (detect_actions) + document_search 신규.
기존 detect_action() 단일 매칭은 backward compat 으로 유지.
"""

import re
from typing import Dict, Literal, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class ActionResult:
    """액션 실행 결과"""
    action_type: str       # "email", "error_code", "employee", "spc", "bridge", "text"
    success: bool
    data: Any              # 액션별 결과 데이터
    display_text: str      # 채팅에 표시할 텍스트
    bridge_target: str = ""  # Feature 이동 대상 (bridge 액션인 경우)


# 액션 키워드 패턴
ACTION_PATTERNS = {
    "error_code": {
        "patterns": [
            r"에러\s*코드\s*([A-Za-z0-9\-]+)",
            r"알람\s*([A-Za-z0-9\-]+)",
            r"(E-\d+|ALM-\d+|SRVO-\d+|COM-[A-Z]-\d+)",
        ],
        "keywords": [
            "에러코드", "에러 코드", "알람", "경고", "고장",
            # v3.4: 설비 증상 키워드 확장
            "설비 이상", "멈춤", "정지", "비상", "소음", "진동",
            "누유", "과열", "마모", "아크", "스패터", "너겟",
            "슬라이드", "유압", "냉각수", "서보",
        ],
    },
    "employee_search": {
        "patterns": [
            r"(.+?)\s*(연락처|전화번호|내선|이메일|메일주소|이메일주소)",
            r"(.+?)\s*(누구|찾아|검색)",
            # v3.5 — 인물 직급 패턴 ("김민수 차장", "박 부장님", "이지영 과장에게")
            r"([가-힣]{1,3})\s*(부장|차장|과장|대리|팀장|본부장|책임|선임|수석|이사|상무|전무)(?:님|에게|께|씨)?",
            # v3.5 — "연락드리는 방법", "어디 있어", "어디 계세요" 같은 자연어 질문
            r"(.+?)\s*(연락|어디|위치|있어|있나|계세요|계신|만나|찾고)",
        ],
        # v3.5 — 키워드 확장 (직급 단어 + 자연어 동사)
        "keywords": [
            "연락처", "전화번호", "내선", "이메일", "담당자",
            "연락", "어디", "위치", "메일", "이메일주소",
            "부장", "차장", "과장", "대리", "팀장", "본부장",
            "선임", "책임", "수석", "이사", "상무", "전무",
        ],
    },
    "spc_status": {
        "patterns": [],
        "keywords": ["SPC", "Cpk", "공정능력", "관리도", "공정 상태", "품질 이상", "Nelson", "관리 한계", "이상 감지"],
    },
    "compose_email": {
        "patterns": [],
        "keywords": ["이메일 보내", "이메일 작성", "메일 써", "메일 보내"],
    },
    "compose_document": {
        "patterns": [],
        "keywords": ["보고서 작성", "보고서 써", "문서 작성", "8D 작성", "ECN 작성"],
    },
    # v3.4: 규제/컴플라이언스 상태 조회
    "regulation_status": {
        "patterns": [],
        "keywords": ["법규", "규제", "관세", "REACH", "산안법", "안전거리", "시행", "컴플라이언스"],
    },
    # v3.3 Phase E — 문서 검색·다운로드 (Module A 인-챗 진입점)
    "document_search": {
        "patterns": [
            r"([A-Za-z가-힣0-9]+)\s*(양식|폼|템플릿|매뉴얼|문서)\s*(찾|검색|다운|어디)",
        ],
        "keywords": [
            "양식 다운", "양식 찾", "양식 어디",
            "매뉴얼 찾", "매뉴얼 검색", "문서 검색", "문서 찾",
            "PPAP 양식", "8D 양식", "ECN 양식", "SOP 다운", "도면 검색",
        ],
    },
}


# v3.3 Phase E — action_type → 5종 카드 kind 매핑.
# spc_status 는 ErrorCard 통합 (Module F 같은 운영 컨텍스트).
ActionKind = Literal["document", "draft", "compliance", "employee", "error"]

ACTION_TYPE_TO_KIND: Dict[str, ActionKind] = {
    "error_code":         "error",
    "spc_status":         "error",
    "employee_search":    "employee",
    "regulation_status":  "compliance",
    "compose_email":      "draft",
    "compose_document":   "draft",
    "document_search":    "document",
}

# 우선순위 (낮은 인덱스 = 높음). 다중 매칭 시 이 순서로 정렬.
_ACTION_PRIORITY = [
    "error_code",
    "employee_search",
    "regulation_status",
    "document_search",
    "compose_document",
    "compose_email",
    "spc_status",
]


@dataclass
class DetectedAction:
    """v3.3 Phase E — 다중 매칭용 액션 디스크립터."""
    action_type: str            # ACTION_PATTERNS 키
    kind: ActionKind            # 5종 카드 kind
    confidence: float           # 0.0~1.0 (정규식=1.0, 키워드=0.7)
    matched_keyword: str = ""   # 매칭된 키워드 또는 정규식 그룹
    params: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.params is None:
            self.params = {}


def detect_action(query: str) -> Optional[Tuple[str, dict]]:
    """
    사용자 질문에서 실행 가능한 액션 감지 (단일 매칭, backward compat).

    Returns:
        (action_type, extracted_params) 또는 None
    """
    query_lower = query.lower().replace(" ", "")

    for action_type, config in ACTION_PATTERNS.items():
        for pattern in config.get("patterns", []):
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return action_type, {"match": match.group(1) if match.groups() else ""}

        for keyword in config.get("keywords", []):
            if keyword.replace(" ", "") in query_lower:
                return action_type, {"keyword": keyword, "query": query}

    return None


def detect_actions(query: str) -> list[DetectedAction]:
    """v3.3 Phase E — 다중 액션 매칭.

    같은 질문이 여러 액션 카테고리에 걸칠 수 있다 (예: "PPAP 양식 + 박성훈 차장 연락처").
    매칭된 모든 액션을 _ACTION_PRIORITY 순서로 정렬해 반환.

    같은 kind 의 액션이 여러 개 매칭되면 가장 높은 confidence 1개만 유지 (중복 카드 방지).
    예: error_code 패턴 매칭 + spc_status 키워드 → 둘 다 'error' kind → 패턴 매칭 1개만.
    """
    if not query or not query.strip():
        return []

    query_lower = query.lower().replace(" ", "")
    detected: list[DetectedAction] = []

    for action_type, config in ACTION_PATTERNS.items():
        kind = ACTION_TYPE_TO_KIND.get(action_type)
        if not kind:
            continue

        # 정규식 매칭 — confidence 1.0
        matched = False
        for pattern in config.get("patterns", []):
            m = re.search(pattern, query, re.IGNORECASE)
            if m:
                detected.append(DetectedAction(
                    action_type=action_type,
                    kind=kind,
                    confidence=1.0,
                    matched_keyword=m.group(0),
                    params={"match": m.group(1) if m.groups() else m.group(0), "query": query},
                ))
                matched = True
                break  # 같은 액션 내 다른 패턴 중복 매칭 방지

        if matched:
            continue

        # 키워드 매칭 — confidence 0.7. 대소문자 무시 (SPC/Cpk/REACH 등 영문 키워드 호환).
        for keyword in config.get("keywords", []):
            if keyword.lower().replace(" ", "") in query_lower:
                detected.append(DetectedAction(
                    action_type=action_type,
                    kind=kind,
                    confidence=0.7,
                    matched_keyword=keyword,
                    params={"keyword": keyword, "query": query},
                ))
                break  # 같은 액션 내 첫 키워드만

    if not detected:
        return []

    # 우선순위 정렬 — _ACTION_PRIORITY index 가 작을수록 먼저
    def _priority(d: DetectedAction) -> int:
        try:
            return _ACTION_PRIORITY.index(d.action_type)
        except ValueError:
            return 999

    detected.sort(key=_priority)

    # 같은 kind 중복 제거 — 우선순위 정렬됐으므로 첫 번째(최우선)만 유지
    seen_kinds: set[str] = set()
    unique: list[DetectedAction] = []
    for d in detected:
        if d.kind in seen_kinds:
            continue
        seen_kinds.add(d.kind)
        unique.append(d)

    return unique


def execute_action(action_type: str, params: dict, query: str) -> ActionResult:
    """액션 실행"""

    if action_type == "error_code":
        return _action_error_code(params, query)
    elif action_type == "employee_search":
        return _action_employee_search(params, query)
    elif action_type == "spc_status":
        return _action_spc_status(params, query)
    elif action_type == "compose_email":
        return ActionResult(
            action_type="bridge", success=True,
            data={"target": "B", "doc_type": "사내 이메일"},
            display_text="이메일 작성 화면으로 이동합니다. 아래 버튼을 클릭하세요.",
            bridge_target="B",
        )
    elif action_type == "compose_document":
        return ActionResult(
            action_type="bridge", success=True,
            data={"target": "B"},
            display_text="문서 작성 화면으로 이동합니다. 아래 버튼을 클릭하세요.",
            bridge_target="B",
        )

    elif action_type == "regulation_status":
        return _action_regulation_status(params, query)

    return ActionResult("text", False, None, "해당 작업을 처리할 수 없습니다.")


def _action_regulation_status(params: dict, query: str) -> ActionResult:
    """v3.4: 규제/컴플라이언스 상태 조회"""
    try:
        from features.compliance.demo_scenario_engine import DemoScenarioEngine
        engine = DemoScenarioEngine()
        summary = engine.get_summary_for_dashboard()
        scenarios = summary.get("scenarios", [])

        if not scenarios:
            return ActionResult("bridge", True, {"target": "D"},
                                "법규 모니터링 화면으로 이동합니다.", bridge_target="D")

        # 특정 시나리오 키워드 매칭
        q_lower = query.lower()
        matched = None
        keyword_map = {
            "safety_distance": ["안전거리", "산안법", "프레스 안전"],
            "us_tariff_25": ["관세", "HMGMA", "트럼프", "25%"],
            "reach_svhc_update": ["REACH", "SVHC", "크롬", "화학물질"],
        }
        for sid, keywords in keyword_map.items():
            if any(kw.lower() in q_lower for kw in keywords):
                matched = engine.get_scenario(sid)
                break

        if matched:
            lines = [
                f"**규제 현황: {matched.title}**\n",
                f"- 심각도: **{matched.severity}** (리스크 {matched.risk_score}/100)",
                f"- 시행일: {matched.effective_date} (D-{matched.days_until_effective})",
                f"- 영향 시설: {', '.join(matched.affected_plants)}",
                f"- 영향 부서: {', '.join(matched.affected_departments)}",
                "",
                "**필요 조치:**",
            ]
            for i, a in enumerate(matched.required_actions[:3], 1):
                lines.append(f"  {i}. {a}")
            if matched.cost_impact:
                lines.append(f"\n- 비용 영향: {matched.cost_impact}")
            lines.append("\n> 상세 시뮬레이션은 Feature D → '시뮬레이션 실행' 버튼에서 확인하세요.")
            return ActionResult("text", True, matched, "\n".join(lines))

        # 전체 요약
        lines = [f"**규제 현황 요약** ({summary['total_scenarios']}건 모니터링 중)\n"]
        for s in scenarios:
            sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🔵"}.get(s.severity, "⚪")
            lines.append(f"{sev_emoji} **{s.title}** — {s.severity} ({s.risk_score}점, D-{s.days_until_effective})")
        lines.append("\n> 상세 분석은 Feature D에서 확인하세요.")
        return ActionResult("text", True, summary, "\n".join(lines))

    except Exception:
        return ActionResult("bridge", True, {"target": "D"},
                            "법규 모니터링 화면으로 이동합니다.", bridge_target="D")


def _action_error_code(params: dict, query: str) -> ActionResult:
    """v3.4: 에러코드 조회 — 패턴 매칭이면 DB 직접 조회, 자연어 증상이면 ML 검색"""
    try:
        code = params.get("match", "")
        if not code:
            match = re.search(r'([A-Za-z]+-?\d+)', query)
            code = match.group(1) if match else ""

        # 에러코드 패턴 매칭 → DB 직접 조회
        if code and re.match(r'^[A-Za-z]+-?\d+$', code):
            from features.equipment.error_code_db import lookup_error
            results = lookup_error(code)
            if results:
                err = results[0]
                display = (
                    f"**에러코드: {err.get('error_code', code)}**\n\n"
                    f"- 장비유형: {err.get('equipment_type', '-')}\n"
                    f"- 설명: {err.get('error_name', '-')}\n"
                    f"- 원인: {err.get('cause', '-')}\n"
                    f"- 조치: {err.get('action', '-')}\n"
                    f"- 심각도: {err.get('severity', '-')}"
                )
                return ActionResult("error_code", True, results, display)
            return ActionResult("error_code", False, None, f"에러코드 '{code}'를 찾을 수 없습니다.")

        # v3.4: 자연어 증상 → ML 통합 검색 (이력 + Markov 포함)
        from features.equipment.ml_error_search import ml_search_with_context
        results = ml_search_with_context(query, top_k=3)
        if results:
            lines = ["**설비 AI 증상 검색 결과** (TF-IDF ML)\n"]
            for i, r in enumerate(results):
                score_pct = round(r["score"] * 100, 1)
                hs = r.get("history_summary") or {}
                hist_info = f" | 최근 3개월 {hs.get('total_count', 0)}회, 평균 복구 {hs.get('avg_resolution_min', 0)}분" if hs.get("total_count") else ""

                lines.append(
                    f"**{i+1}. {r['code']}** (유사도 {score_pct}%) — {r['equipment_type']}\n"
                    f"  - {r['description']}\n"
                    f"  - 원인: {r['cause']}\n"
                    f"  - 조치: {r['action']}{hist_info}\n"
                )

            # TOP-1 연쇄 경고
            cascade = results[0].get("cascade_warning")
            if cascade and cascade.get("predictions"):
                lines.append("\n⚠️ **연쇄 고장 예측:**")
                for p in cascade["predictions"][:2]:
                    lines.append(f"  - {p['code']} ({p['probability']:.0f}%) — {p['description']}")

            lines.append("\n> 상세 분석은 Feature F → '매뉴얼 AI' 탭에서 확인하세요.")
            return ActionResult("text", True, results, "\n".join(lines))

        return ActionResult("error_code", False, None, "유사한 에러코드를 찾을 수 없습니다.")
    except Exception as e:
        return ActionResult("error_code", False, None, f"에러코드 조회 중 오류: {str(e)}")


def _action_employee_search(params: dict, query: str) -> ActionResult:
    """인원 검색 액션"""
    try:
        search_term = params.get("match", params.get("query", ""))
        search_term = re.sub(r'(연락처|전화번호|내선|이메일|누구|찾아|검색|알려줘)', '', search_term).strip()

        if search_term:
            from features.search.employee.database import EmployeeDatabase
            from features.search.employee.search import EmployeeSearchEngine
            db = EmployeeDatabase()
            engine = EmployeeSearchEngine(db)
            result = engine.search(search_term)
            db.close()

            employees = result.get("results", [])
            if employees:
                lines = [f"**'{search_term}' 검색 결과 ({len(employees)}건)**\n"]
                for emp in employees[:3]:
                    lines.append(
                        f"- **{emp.get('name', '')}** | {emp.get('department', '')} "
                        f"{emp.get('position', '')} | 내선: {emp.get('extension', '-')} "
                        f"| {emp.get('email', '-')}"
                    )
                return ActionResult("employee", True, employees, "\n".join(lines))

        return ActionResult("employee", False, None, f"'{search_term}' 검색 결과가 없습니다.")
    except Exception as e:
        return ActionResult("employee", False, None, f"인원 검색 오류: {str(e)}")


def _action_spc_status(params: dict, query: str) -> ActionResult:
    """v3.4: SPC 현황 조회 — 실제 공정 건강 데이터 반환"""
    try:
        from features.equipment.spc_dashboard import SPCDashboard
        dashboard = SPCDashboard()
        summary = dashboard.get_summary()
        health_list = summary.get("health_list", [])

        if not health_list:
            return ActionResult(
                "bridge", True, {"target": "F"},
                "SPC 공정 데이터를 불러올 수 없습니다. Feature F 'SPC 분석' 탭에서 확인하세요.",
                bridge_target="F",
            )

        # 텍스트 요약 생성
        lines = [f"**SPC 공정 현황** ({summary['total_processes']}개 공정 모니터링 중)\n"]

        critical = [h for h in health_list if h.status == "critical"]
        warning = [h for h in health_list if h.status == "warning"]
        good = [h for h in health_list if h.status == "good"]

        if critical:
            lines.append(f"🔴 **긴급** ({len(critical)}건):")
            for h in critical:
                rules = ", ".join(f"Rule {r}" for r in h.violated_rules) if h.violated_rules else ""
                lines.append(f"  - {h.process_name}: Cpk {h.current_cpk:.3f}, 위반 {h.violation_count}건 ({rules})")

        if warning:
            lines.append(f"\n🟡 **주의** ({len(warning)}건):")
            for h in warning:
                lines.append(f"  - {h.process_name}: Cpk {h.current_cpk:.3f}, 위반 {h.violation_count}건")

        if good:
            lines.append(f"\n🟢 **정상** ({len(good)}건): {', '.join(h.process_name for h in good)}")

        lines.append(f"\n총 Nelson Rule 위반: **{summary['total_violations']}건**")
        lines.append("\n> 상세 분석은 Feature F → 'SPC 분석' 탭에서 확인하세요.")

        return ActionResult("text", True, summary, "\n".join(lines))

    except Exception:
        return ActionResult(
            "bridge", True, {"target": "F"},
            "SPC 공정 분석 화면으로 이동합니다. Feature F의 'SPC 분석' 탭에서 확인하세요.",
            bridge_target="F",
        )
