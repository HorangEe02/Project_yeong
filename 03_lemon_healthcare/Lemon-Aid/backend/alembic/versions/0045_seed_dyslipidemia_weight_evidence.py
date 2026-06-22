"""Seed reviewed evidence for dyslipidemia and weight management.

Adds 6 new evidence items:
  - dyslipidemia_saturated_fat_reduction
  - dyslipidemia_omega3_fish_sources
  - triglyceride_sugar_alcohol_reduction
  - weight_management_plate_composition
  - weight_management_meal_timing
  - weight_management_record_pattern_review

Revision ID: 0045_seed_dyslipidemia_weight_evidence
Revises: 0044_normalize_check_constraint_names
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0045_seed_dyslipidemia_weight_evidence"
down_revision: str | None = "0044_normalize_check_constraint_names"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed dyslipidemia and weight management evidence items."""
    for evidence in _evidence_rows():
        op.execute(_insert_evidence_sql(**evidence))


def downgrade() -> None:
    """Remove seeded dyslipidemia and weight management evidence records."""
    topics = "', '".join(row["topic"] for row in _evidence_rows())
    op.execute(f"""
        DELETE FROM medical_evidence_items
        WHERE topic IN ('{topics}');
        """)


def _insert_evidence_sql(
    *,
    evidence_id: str,
    source_id: str,
    topic: str,
    claim_summary: str,
    allowed_user_wording: str,
    blocked_wording: str,
    applicability_note: str,
    caution_level: str,
    specific_examples: tuple[str, ...],
    checklist: tuple[str, ...],
    caution_conditions: tuple[str, ...],
    must_not_say: tuple[str, ...],
) -> str:
    return f"""
        INSERT INTO medical_evidence_items (
            id, source_version_id, topic, audience, claim_summary,
            allowed_user_wording, blocked_wording, applicability_note,
            specific_examples, checklist, caution_conditions, must_not_say,
            caution_level, review_status, algorithm_version
        )
        SELECT
            '{evidence_id}'::uuid,
            (
                SELECT id
                FROM medical_source_versions
                WHERE source_id = '{source_id}'
                  AND review_status = 'reviewed'
                  AND expires_at >= CURRENT_DATE
                ORDER BY reviewed_at DESC
                LIMIT 1
            ),
            '{topic}',
            'adult',
            {claim_summary!r},
            {allowed_user_wording!r},
            {blocked_wording!r},
            {applicability_note!r},
            '{_json_array(specific_examples)}'::jsonb,
            '{_json_array(checklist)}'::jsonb,
            '{_json_array(caution_conditions)}'::jsonb,
            '{_json_array(must_not_say)}'::jsonb,
            '{caution_level}',
            'reviewed',
            'answer-card-seed-2026-06-13'
        WHERE NOT EXISTS (
            SELECT 1
            FROM medical_evidence_items
            WHERE topic = '{topic}'
              AND audience = 'adult'
              AND review_status = 'reviewed'
        );
    """


def _json_array(values: tuple[str, ...]) -> str:
    escaped = [value.replace("\\", "\\\\").replace('"', '\\"') for value in values]
    return "[" + ", ".join(f'"{value}"' for value in escaped) + "]"


def _evidence_rows() -> tuple[dict[str, object], ...]:
    return (
        # ── 고지혈증 (Dyslipidemia) ──────────────────────────────────────────
        {
            "evidence_id": "bbbbbbbb-0001-4000-8000-000000000001",
            "source_id": "cdc-public-health",
            "topic": "dyslipidemia_saturated_fat_reduction",
            "claim_summary": (
                "Reducing saturated fat (red meat, full-fat dairy, processed foods) "
                "and eliminating trans fat helps manage LDL cholesterol. "
                "Replace with unsaturated fats such as olive oil, nuts, and fish."
            ),
            "allowed_user_wording": (
                "소고기·삼겹살 대신 생선이나 닭가슴살을 선택하고, "
                "버터 대신 올리브오일을 쓴다. "
                "가공식품 성분표에서 포화지방과 트랜스지방 함량을 확인한다."
            ),
            "blocked_wording": (
                "LDL이 정상화됩니다. 약이 필요 없어집니다. "
                "코코넛오일은 괜찮습니다. 콜레스테롤이 치료됩니다."
            ),
            "applicability_note": "고지혈증(이상지질혈증) 또는 LDL·총콜레스테롤 관리 관련 식이 질문",
            "caution_level": "caution",
            "specific_examples": (
                "소고기·삼겹살 → 생선·닭가슴살·두부로 대체",
                "버터·마가린 → 올리브오일·카놀라유로 대체",
                "가공식품 성분표 트랜스지방 0g 확인",
                "견과류(호두·아몬드) 소량 간식",
            ),
            "checklist": (
                "포화지방 많은 음식 섭취 빈도(주 몇 회)",
                "가공식품·패스트푸드 섭취량",
                "현재 스타틴 등 지질강하제 복용 여부",
                "최근 혈액검사 LDL·HDL·총콜레스테롤 수치",
            ),
            "caution_conditions": (
                "스타틴 계열 약 복용 중 → 자몽·자몽주스 섭취 금지 여부 확인 권고",
                "가족성 고콜레스테롤혈증 의심 → 전문의 상담 권고",
                "심혈관 질환 병력 → 식이 변경 전 의사 확인 권고",
            ),
            "must_not_say": (
                "LDL이 정상화됩니다",
                "약이 필요 없어집니다",
                "코코넛오일은 포화지방이지만 괜찮습니다",
                "콜레스테롤이 치료됩니다",
                "처방을 바꾸세요",
            ),
        },
        {
            "evidence_id": "bbbbbbbb-0001-4000-8000-000000000002",
            "source_id": "cdc-public-health",
            "topic": "dyslipidemia_omega3_fish_sources",
            "claim_summary": (
                "Fatty fish rich in omega-3 (mackerel, Pacific saury, salmon, herring) "
                "are recommended twice weekly as part of a heart-healthy diet."
            ),
            "allowed_user_wording": (
                "고등어·삼치·연어·청어 같은 등푸른 생선을 주 2회 구이나 찜으로 먹는다."
            ),
            "blocked_wording": (
                "혈중 지방이 내려갑니다. 오메가-3 캡슐이 생선보다 효과적입니다. "
                "생선을 매일 먹으면 콜레스테롤이 정상화됩니다."
            ),
            "applicability_note": "고지혈증 또는 심혈관 건강 관련 식품 질문",
            "caution_level": "info",
            "specific_examples": (
                "고등어 구이",
                "삼치 조림",
                "연어 찜 또는 샐러드",
                "청어 구이",
            ),
            "checklist": (
                "현재 등푸른 생선 섭취 빈도",
                "생선 알레르기 여부",
                "항응고제(와파린·아스피린) 복용 여부",
            ),
            "caution_conditions": (
                "와파린(항응고제) 복용 중 → 오메가-3 고용량 섭취 전 의사 확인 권고",
                "생선 알레르기 → 섭취 전 확인 필요",
            ),
            "must_not_say": (
                "혈중 지방이 내려갑니다",
                "오메가-3 캡슐이 생선보다 효과적입니다",
                "매일 먹으면 콜레스테롤이 정상화됩니다",
                "와파린과 함께 먹어도 됩니다",
            ),
        },
        {
            "evidence_id": "bbbbbbbb-0001-4000-8000-000000000003",
            "source_id": "kdca-healthinfo",
            "topic": "triglyceride_sugar_alcohol_reduction",
            "claim_summary": (
                "High triglycerides are strongly associated with excess simple sugar "
                "and alcohol intake. Reducing sugary drinks, sweets, and alcohol "
                "is the primary dietary goal."
            ),
            "allowed_user_wording": (
                "탄산음료·과일주스 대신 물이나 녹차를 마시고, "
                "과자·사탕 간식을 줄이며, 음주 횟수를 낮춘다."
            ),
            "blocked_wording": (
                "중성지방이 약 없이 정상화됩니다. 탄수화물을 완전히 끊으세요. "
                "과일은 많이 먹어도 됩니다. 술은 와인만 괜찮습니다."
            ),
            "applicability_note": "중성지방(트리글리세리드) 높음 또는 고지혈증 관련 당분·알코올 식이 질문",
            "caution_level": "caution",
            "specific_examples": (
                "탄산음료·과일주스 → 물·녹차로 대체",
                "과자·사탕 → 견과류 소량으로 대체",
                "음주 횟수 줄이기(주 1회 미만 목표)",
                "흰쌀·흰빵 → 현미·통밀로 일부 대체",
            ),
            "checklist": (
                "당분 음료 섭취 빈도(주 몇 회)",
                "과자·단 간식 섭취량",
                "음주 빈도 및 음주량",
                "당뇨 동반 여부",
            ),
            "caution_conditions": (
                "당뇨를 동반한 경우 → 당분 줄이기와 혈당 변화를 함께 모니터링 권고",
                "알코올 의존성 의심 → 전문가 상담 권고",
                "지질강하제 복용 중 → 임의로 약 중단하지 말 것",
            ),
            "must_not_say": (
                "중성지방이 약 없이 정상화됩니다",
                "탄수화물을 완전히 끊으세요",
                "과일은 천연 당분이라 많이 먹어도 됩니다",
                "와인은 심장에 좋아서 괜찮습니다",
                "처방을 바꾸세요",
            ),
        },
        # ── 체중 관리 (Weight Management) ────────────────────────────────────
        {
            "evidence_id": "bbbbbbbb-0001-4000-8000-000000000004",
            "source_id": "cdc-public-health",
            "topic": "weight_management_plate_composition",
            "claim_summary": (
                "A balanced plate for weight management: half non-starchy vegetables, "
                "one quarter lean protein, one quarter complex carbohydrates."
            ),
            "allowed_user_wording": (
                "식판의 절반을 비전분 채소(브로콜리·양상추·오이 등)로 채우고, "
                "1/4은 단백질(닭가슴살·두부·생선), 나머지 1/4은 복합 탄수화물(현미·고구마·통밀)로 구성한다."
            ),
            "blocked_wording": (
                "이렇게 하면 살이 빠집니다. 이 양만 드세요. "
                "탄수화물은 완전히 끊어야 합니다. 칼로리를 극단적으로 줄이세요."
            ),
            "applicability_note": "체중 관리 또는 식이요법 중 식사 구성 방법 질문",
            "caution_level": "info",
            "specific_examples": (
                "비전분 채소: 브로콜리·양상추·오이·피망·양배추",
                "단백질: 닭가슴살·두부·생선·달걀·콩류",
                "복합 탄수화물: 현미·고구마·통밀빵·귀리",
            ),
            "checklist": (
                "현재 식판 구성에서 채소 비중",
                "단백질 공급원 다양성",
                "정제 탄수화물(흰밥·흰빵·과자) 섭취 비중",
                "의사 처방 식이요법 진행 중 여부",
            ),
            "caution_conditions": (
                "의사·영양사가 처방한 식이요법 중 → 기존 계획 우선 따르도록 안내",
                "신장 질환 → 단백질 제한 필요 여부 확인 권고",
            ),
            "must_not_say": (
                "이렇게 하면 살이 빠집니다",
                "이 양만 드세요",
                "탄수화물을 완전히 끊어야 합니다",
                "칼로리를 극단적으로 줄이세요",
                "체중이 몇 kg 빠집니다",
            ),
        },
        {
            "evidence_id": "bbbbbbbb-0001-4000-8000-000000000005",
            "source_id": "cdc-public-health",
            "topic": "weight_management_meal_timing",
            "claim_summary": (
                "Regular meal intervals (4-6 hours apart) and avoiding late-night eating "
                "help prevent overeating and excessive nighttime calorie intake."
            ),
            "allowed_user_wording": (
                "식사 간격을 4~6시간으로 유지하고, "
                "저녁 식사 후 야식을 줄인다. "
                "규칙적인 식사 시간을 지키는 것이 과식 예방에 도움이 된다."
            ),
            "blocked_wording": (
                "간헐적 단식이 가장 효과적입니다. 몇 시 이후로는 먹으면 안 됩니다. "
                "하루 한 끼만 먹어야 합니다. 야식만 끊으면 살이 빠집니다."
            ),
            "applicability_note": "체중 관리 중 식사 시간·야식·끼니 패턴 관련 질문",
            "caution_level": "info",
            "specific_examples": (
                "아침 8시 → 점심 12~1시 → 저녁 6~7시 예시",
                "야식 대신 허브티 또는 물",
                "배고픔과 습관적 간식 구분하기",
            ),
            "checklist": (
                "현재 식사 간격 패턴",
                "야식 빈도(주 몇 회)",
                "당뇨 또는 저혈당 위험 여부",
            ),
            "caution_conditions": (
                "당뇨약(인슐린·설폰요소제) 복용 중 → 식사 간격 변경 시 저혈당 위험, 의사 확인 권고",
                "임신 중 → 식이 변경 전 산부인과 의사 확인 권고",
            ),
            "must_not_say": (
                "간헐적 단식이 가장 효과적입니다",
                "몇 시 이후로는 절대 먹으면 안 됩니다",
                "하루 한 끼만 드세요",
                "야식만 끊으면 살이 빠집니다",
            ),
        },
        {
            "evidence_id": "bbbbbbbb-0001-4000-8000-000000000006",
            "source_id": "cdc-public-health",
            "topic": "weight_management_record_pattern_review",
            "claim_summary": (
                "Reviewing weight records alongside meal logs helps identify patterns "
                "such as late-night eating frequency, meal composition imbalances, "
                "and portion trends over time."
            ),
            "allowed_user_wording": (
                "체중 기록과 식사 기록을 함께 살펴보면 "
                "야식 빈도, 과식 패턴, 식품 구성 문제를 파악하는 데 도움이 된다."
            ),
            "blocked_wording": (
                "기록만으로 체중이 줄어듭니다. 이 패턴은 문제입니다. "
                "전문가 상담이 필요 없습니다. 기록하면 반드시 살이 빠집니다."
            ),
            "applicability_note": "헬스 기록(체중·식사) 활용 방법 또는 기록 패턴 해석 질문",
            "caution_level": "info",
            "specific_examples": (
                "주간 체중 변화 그래프와 야식 빈도 비교",
                "식사 기록에서 채소·단백질·탄수화물 비중 확인",
                "과식 발생 시간대 파악(오후 늦은 시간·야간)",
            ),
            "checklist": (
                "기록 주기(매일 vs 불규칙)",
                "야식 빈도(주 몇 회)",
                "주간 체중 변화 추이",
                "식품 구성 편중 여부(채소 부족, 탄수화물 과다 등)",
            ),
            "caution_conditions": (
                "체중 변화가 급격하거나(주 1kg 이상 증감) 원인 불명 → 전문가 상담 권고",
                "식이장애 의심 → 의료 전문가 상담 권고",
            ),
            "must_not_say": (
                "기록만으로 체중이 줄어듭니다",
                "이 패턴은 문제입니다",
                "전문가 상담이 필요 없습니다",
                "기록하면 반드시 살이 빠집니다",
                "이 체중은 정상입니다",
            ),
        },
    )
