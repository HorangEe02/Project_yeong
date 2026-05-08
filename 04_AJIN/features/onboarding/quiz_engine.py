"""
대화형 학습 퀴즈 엔진
- SOP 단계별 확인 퀴즈 자동 생성
- 용어집 기반 용어 퀴즈
- 커리큘럼 단계 완료 검증
"""

import random
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class QuizQuestion:
    """퀴즈 문제"""
    question: str
    options: List[str]         # 4지선다
    correct_index: int         # 정답 인덱스 (0~3)
    explanation: str           # 정답 해설
    category: str              # "sop", "glossary", "safety"
    difficulty: str = "basic"  # "basic", "intermediate", "advanced"
    source_id: str = ""        # SOP ID 또는 용어 ID
    related_step: int = 0      # v3.4: 퀴즈 출제 근거 SOP 단계 번호 (오답 재학습용)


def generate_sop_quiz(sop_id: str, step_number: int = None) -> Optional[QuizQuestion]:
    """SOP 단계 기반 퀴즈 생성"""
    from features.onboarding.sop_guide import SOP_DATABASE

    sop = SOP_DATABASE.get(sop_id)
    if not sop:
        return None

    if step_number:
        steps = [s for s in sop.steps if s.step_number == step_number]
    else:
        steps = sop.steps

    if not steps:
        return None

    step = random.choice(steps)
    quiz_type = random.choice(["checklist", "caution", "order"])

    if quiz_type == "checklist" and step.checklist:
        correct = random.choice(step.checklist)
        wrong_items = _generate_distractors_checklist(correct, sop)
        return _build_question(
            question=f"'{step.title}' 단계에서 반드시 확인해야 할 항목은?",
            correct=correct,
            distractors=wrong_items,
            explanation=f"'{step.title}' 단계의 체크리스트: {', '.join(step.checklist)}",
            category="sop",
            source_id=sop_id,
            related_step=step.step_number,
        )

    elif quiz_type == "caution" and step.caution:
        return QuizQuestion(
            question=f"'{step.title}' 단계에서 특히 주의해야 할 사항은?",
            options=[
                step.caution,
                "작업 속도를 최대로 올린다",
                "보호구 없이도 작업 가능하다",
                "다른 작업자가 있어도 진행한다",
            ],
            correct_index=0,
            explanation=f"주의사항: {step.caution}",
            category="safety",
            source_id=sop_id,
            related_step=step.step_number,
        )

    else:  # order
        if len(sop.steps) >= 3:
            correct_order = f"1단계: {sop.steps[0].title}"
            wrong_orders = [
                f"1단계: {sop.steps[-1].title}",
                f"1단계: {sop.steps[len(sop.steps) // 2].title}",
                "순서 무관하게 진행 가능",
            ]
            return _build_question(
                question=f"'{sop.title}'에서 가장 먼저 수행하는 단계는?",
                correct=correct_order,
                distractors=wrong_orders,
                explanation=f"올바른 순서: {' -> '.join(s.title for s in sop.steps)}",
                category="sop",
                source_id=sop_id,
                related_step=sop.steps[0].step_number,
            )

    return None


def generate_glossary_quiz(
    glossary_items: List[Dict],
    department: str = "",
) -> Optional[QuizQuestion]:
    """용어집 기반 퀴즈 생성"""
    if len(glossary_items) < 4:
        return None

    correct_item = random.choice(glossary_items)
    wrong_items = random.sample(
        [g for g in glossary_items if g != correct_item],
        min(3, len(glossary_items) - 1),
    )

    return _build_question(
        question=f"'{correct_item.get('term', '')}'의 올바른 설명은?",
        correct=correct_item.get("definition", "")[:80],
        distractors=[w.get("definition", "")[:80] for w in wrong_items],
        explanation=f"{correct_item.get('term', '')}: {correct_item.get('definition', '')}",
        category="glossary",
    )


def _build_question(
    question: str,
    correct: str,
    distractors: List[str],
    explanation: str,
    category: str,
    source_id: str = "",
    related_step: int = 0,
) -> QuizQuestion:
    """4지선다 문제 조립 (선택지 셔플)"""
    options = [correct] + distractors[:3]
    random.shuffle(options)
    correct_index = options.index(correct)

    return QuizQuestion(
        question=question,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
        category=category,
        source_id=source_id,
        related_step=related_step,
    )


def _generate_distractors_checklist(correct: str, sop) -> List[str]:
    """체크리스트 오답 생성"""
    all_items = []
    for step in sop.steps:
        all_items.extend(step.checklist)
    wrong = [item for item in all_items if item != correct]
    if len(wrong) < 3:
        wrong.extend(["해당 사항 없음", "자동으로 처리됨", "생략 가능"])
    return random.sample(wrong, min(3, len(wrong)))
