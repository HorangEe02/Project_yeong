"""
부서 간 협업 시나리오 가이드 (v3.4)

신입사원이 타 부서로부터 요청을 받았을 때:
- 내가 준비해야 할 것 (my_actions)
- 넘겨야 할 부서/담당자 (hand_off_to)
- 예상 소요 시간 (deadline_info)
- 관련 SOP 연결 (related_sop_id)
LLM 미호출, 룰 기반 즉시 응답.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List


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


COLLABORATION_SCENARIOS: List[CollaborationScenario] = [
    CollaborationScenario(
        id="COLLAB-8D",
        trigger_keywords=["8D", "8d", "클레임", "불량 보고", "시정 조치", "클레임 대응"],
        situation="완성차(현대/기아)에서 납품 부품 클레임 접수 → 품질팀에서 관련 부서에 8D 자료 요청",
        requesting_dept="품질보증팀",
        my_actions=[
            "해당 부품의 최근 생산 이력 확인 (생산 일시, 설비, 작업자, 로트 번호)",
            "불량 현상 관련 공정 조건 데이터 수집 (프레스 조건, 용접 전류 등)",
            "해당 로트의 검사 기록 확인 (자주검사, 순회검사 데이터)",
            "유사 불량 과거 발생 여부 확인",
        ],
        hand_off_to="품질보증팀 8D 담당자",
        hand_off_items=[
            "생산 이력 (로트 번호, 생산일시, 설비명)",
            "공정 조건 데이터 (해당 시점의 설정값)",
            "검사 기록 (해당 로트 자주검사 결과)",
            "불량 관련 사진 (있으면)",
        ],
        deadline_info="현대차 SQ 기준 8D 회신 기한: 클레임 접수 후 5영업일 이내",
        related_sop_id="SOP-8D",
        tips=[
            "품질팀에 넘길 때 로트 번호를 반드시 포함해야 추적이 가능합니다",
            "'작업자 부주의'로 원인을 적으면 SQ에서 반려됩니다 — 시스템적 원인을 찾아주세요",
            "모르는 부분은 '확인 중'이라 표기하고, 가진 자료부터 빠르게 전달하세요",
        ],
    ),
    CollaborationScenario(
        id="COLLAB-ECN",
        trigger_keywords=["ECN", "설계변경", "도면 변경", "리비전 변경"],
        situation="완성차/연구소로부터 설계 변경 통보(ECN)가 내려와서 관련 부서에 영향 파악 요청",
        requesting_dept="부품개발팀",
        my_actions=[
            "변경 내용이 내 공정에 영향 있는지 확인 (치수/소재/공법 변경 여부)",
            "영향 있다면 금형 수정 필요 여부 판단",
            "현재 재고(변경 전 부품) 수량 확인",
            "전환 시점에 맞춰 생산 계획 조정 가능 여부 확인",
        ],
        hand_off_to="부품개발팀 ECN 담당자",
        hand_off_items=[
            "영향 유무 회신 (영향 있음/없음)",
            "금형 수정 필요 시: 예상 기간 + 비용 견적",
            "현 재고 수량 및 전환 가능 시점",
            "Control Plan/FMEA 변경 필요 여부",
        ],
        deadline_info="ECN 영향 파악 회신: 접수 후 통상 3영업일 이내",
        related_sop_id="SOP-ECN",
        tips=[
            "ECN 적용 시점(즉시/재고 소진 후)을 반드시 확인하세요",
            "금형 수정이 필요하면 구매팀에도 동시 통보해야 합니다",
        ],
    ),
    CollaborationScenario(
        id="COLLAB-SPC-DATA",
        trigger_keywords=["SPC", "공정 능력", "Cpk", "관리도", "측정 데이터"],
        situation="품질팀 또는 완성차 SQ에서 특정 공정의 SPC 데이터(관리도, Cpk) 요청",
        requesting_dept="품질보증팀",
        my_actions=[
            "요청 부품/공정의 측정 데이터 추출 (해당 기간)",
            "X-bar R 관리도 작성",
            "Cpk 계산 (기준: Cpk >= 1.33)",
            "이상점(관리 한계 이탈) 유무 확인 및 조치 이력 정리",
        ],
        hand_off_to="품질보증팀 SPC 담당",
        hand_off_items=[
            "관리도 (X-bar R Chart) 이미지/파일",
            "Cpk 산출 결과표",
            "이상점 발생 시 조치 이력",
        ],
        deadline_info="정기 보고: 월 1회 / 긴급 요청: 2영업일 이내",
        tips=[
            "Cpk < 1.33이면 공정 능력 부족 판정 — 사전 확인하세요",
            "AI 시스템의 SPC 분석 기능(Feature F)에서 자동 관리도 생성 가능합니다",
        ],
    ),
    CollaborationScenario(
        id="COLLAB-PPAP-PREP",
        trigger_keywords=["PPAP", "승인 서류", "초도품", "양산 승인"],
        situation="신차 부품 양산을 위해 PPAP 서류 패키지 구성, 각 부서별 산출물 취합 필요",
        requesting_dept="부품개발팀",
        my_actions=[
            "내 부서 담당 산출물 확인 (PPAP 18항목 중 해당 항목)",
            "산출물 작성 또는 최신화",
            "제출 기한 확인 및 일정 조율",
        ],
        hand_off_to="부품개발팀 PPAP 총괄",
        hand_off_items=[
            "생산기술팀: 공정 FMEA, Process Flow",
            "품질보증팀: Control Plan, MSA, SPC 초기 데이터",
            "구매팀: 원자재 성적서, 하청 업체 인증서",
            "금형생산팀: 금형 이력카드, 금형 검수 성적서",
        ],
        deadline_info="PPAP 전체 패키지 제출: 양산 전 최소 4주 전",
        related_sop_id="SOP-PPAP",
        tips=[
            "PPAP는 부서 간 협업이 핵심 — 자기 부서 산출물만 잘 내도 큰 기여",
            "항목 간 불일치(FMEA vs Control Plan)가 가장 흔한 반려 사유입니다",
        ],
    ),
    CollaborationScenario(
        id="COLLAB-SAFETY-AUDIT",
        trigger_keywords=["안전 점검", "안전 감사", "안보팀", "점검 대비", "산안법"],
        situation="안전보건팀 또는 외부 기관(고용노동부 등) 안전 점검 예정, 현장 정비 요청",
        requesting_dept="안전보건팀",
        my_actions=[
            "작업장 5S(정리/정돈/청소/청결/습관화) 점검",
            "안전 장구 비치 상태 확인 (안전모, 귀마개, 보안경 등)",
            "비상구/소화기/비상정지 버튼 접근 경로 확보",
            "MSDS(물질안전보건자료) 게시 상태 확인",
            "위험 기계/구역 안전 표지판 부착 상태 확인",
        ],
        hand_off_to="안전보건팀 점검 담당자",
        hand_off_items=[
            "작업장 자체 점검 체크리스트 (완료 상태)",
            "미비 사항 조치 현황 (사진 포함)",
        ],
        deadline_info="내부 점검: 통보 후 3일 이내 / 외부 감사: 1주 전 사전 통보",
        tips=[
            "안전 점검에서 가장 많이 지적되는 항목: MSDS 미게시, 소화기 유효기간 만료",
            "비상구 앞 적재물은 즉시 제거해야 합니다 — 벌금 부과 대상",
        ],
    ),
]


def match_collaboration(query: str, division: str = "", lang: str = "ko") -> Optional[CollaborationScenario]:
    """사용자 질문에서 협업 시나리오 매칭.

    DB(scenarios.db) 우선, 비어있으면 코드 시드 fallback.
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
        # DB 실패 시 코드 시드 fallback (안전장치)
        pass

    # 코드 시드 fallback
    q_lower = (query or "").lower()
    for scenario in COLLABORATION_SCENARIOS:
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
