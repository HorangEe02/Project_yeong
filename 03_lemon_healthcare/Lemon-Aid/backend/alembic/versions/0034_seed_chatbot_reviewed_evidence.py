"""Seed reviewed chatbot evidence records.

Revision ID: 0034_seed_chatbot_reviewed_evidence
Revises: 0033_add_chatbot_unknown_backlog
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0034_seed_chatbot_reviewed_evidence"
down_revision: str | None = "0033_add_chatbot_unknown_backlog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed the initial reviewed evidence coverage for DB-backed chatbot answers."""
    op.execute("""
        INSERT INTO medical_sources (
            id, source_family, publisher, title, canonical_url, jurisdiction,
            source_type, default_review_status, owner
        )
        VALUES
            (
                'kdris-2025', 'nutrition_reference', 'Korean Nutrition Society',
                'Korean Dietary Reference Intakes',
                'https://www.kns.or.kr/FileRoom/FileRoom.asp?BoardID=Kdr',
                'KR', 'reference_intake', 'reviewed', 'Nutrition backend data review'
            ),
            (
                'cdc-public-health', 'general_medical', 'Centers for Disease Control and Prevention',
                'CDC Public Health Guidance', 'https://www.cdc.gov/',
                'US', 'public_health', 'reviewed', 'AI Agent medical knowledge review'
            ),
            (
                'niddk-diabetes-living', 'chronic_condition',
                'National Institute of Diabetes and Digestive and Kidney Diseases',
                'NIDDK Healthy Living with Diabetes',
                'https://www.niddk.nih.gov/health-information/diabetes/overview/diet-eating-physical-activity',
                'US', 'public_health', 'reviewed', 'AI Agent medical knowledge review'
            ),
            (
                'niddk-kidney-disease', 'chronic_condition',
                'National Institute of Diabetes and Digestive and Kidney Diseases',
                'NIDDK Kidney Disease',
                'https://www.niddk.nih.gov/health-information/kidney-disease',
                'US', 'public_health', 'reviewed', 'AI Agent medical knowledge review'
            ),
            (
                'nih-ods-magnesium', 'supplement_reference', 'NIH Office of Dietary Supplements',
                'NIH ODS Magnesium Fact Sheet',
                'https://ods.od.nih.gov/factsheets/Magnesium-Consumer/',
                'US', 'public_health', 'reviewed', 'AI Agent medical knowledge review'
            ),
            (
                'kdca-healthinfo', 'public_health_guidance', 'Korea Disease Control and Prevention Agency',
                'KDCA National Health Information Portal', 'https://health.kdca.go.kr/healthinfo',
                'KR', 'public_health', 'reviewed', 'AI Agent medical knowledge review'
            ),
            (
                'mfds-drug-safety', 'drug_safety_boundary', 'Ministry of Food and Drug Safety',
                'MFDS Drug Safety Portal', 'https://nedrug.mfds.go.kr',
                'KR', 'regulator', 'reviewed', 'AI Agent medical knowledge review'
            )
        ON CONFLICT (id) DO UPDATE SET
            source_family = EXCLUDED.source_family,
            publisher = EXCLUDED.publisher,
            title = EXCLUDED.title,
            canonical_url = EXCLUDED.canonical_url,
            jurisdiction = EXCLUDED.jurisdiction,
            source_type = EXCLUDED.source_type,
            default_review_status = EXCLUDED.default_review_status,
            owner = EXCLUDED.owner,
            updated_at = now();
        """)
    op.execute("""
        INSERT INTO medical_source_versions (
            id, source_id, version_label, published_at, reviewed_at, expires_at,
            review_status, reviewer, review_note
        )
        SELECT *
        FROM (VALUES
            (
                '22222222-2222-4222-8222-222222222222'::uuid,
                'kdris-2025', 'KDRIs 2025', NULL::date, '2026-05-19'::date,
                '2027-05-19'::date, 'reviewed', 'Nutrition backend data review',
                'Seeded for chatbot sodium and food-candidate AnswerCards.'
            ),
            (
                '33333333-3333-4333-8333-333333333333'::uuid,
                'cdc-public-health', '2026-05 MVP source registry', NULL::date,
                '2026-05-29'::date, '2026-11-29'::date, 'reviewed',
                'AI Agent medical knowledge review',
                'Seeded for diabetes, activity, sleep, and symptom AnswerCards.'
            ),
            (
                '44444444-4444-4444-8444-444444444444'::uuid,
                'niddk-diabetes-living', '2026-05 MVP source registry', NULL::date,
                '2026-05-29'::date, '2026-11-29'::date, 'reviewed',
                'AI Agent medical knowledge review',
                'Seeded for diabetes healthy-living AnswerCards.'
            ),
            (
                '55555555-5555-4555-8555-555555555555'::uuid,
                'niddk-kidney-disease', '2026-05 MVP source registry', NULL::date,
                '2026-05-29'::date, '2026-11-29'::date, 'reviewed',
                'AI Agent medical knowledge review',
                'Seeded for kidney disease meal-caution AnswerCards.'
            ),
            (
                '11111111-1111-4111-8111-111111111111'::uuid,
                'nih-ods-magnesium', '2026-05 MVP source registry', NULL::date,
                '2026-05-29'::date, '2026-11-29'::date, 'reviewed',
                'AI Agent medical knowledge review',
                'Seeded for magnesium supplement caution AnswerCards.'
            ),
            (
                '66666666-6666-4666-8666-666666666666'::uuid,
                'kdca-healthinfo', '2026-05 MVP source registry', NULL::date,
                '2026-05-22'::date, '2026-11-22'::date, 'reviewed',
                'AI Agent medical knowledge review',
                'Seeded for Korean public-health wording boundaries.'
            ),
            (
                '77777777-7777-4777-8777-777777777777'::uuid,
                'mfds-drug-safety', '2026-05 MVP source registry', NULL::date,
                '2026-05-22'::date, '2026-11-22'::date, 'reviewed',
                'AI Agent medical knowledge review',
                'Seeded for supplement label-check AnswerCards.'
            )
        ) AS seed(
            id, source_id, version_label, published_at, reviewed_at, expires_at,
            review_status, reviewer, review_note
        )
        WHERE NOT EXISTS (
            SELECT 1
            FROM medical_source_versions existing
            WHERE existing.source_id = seed.source_id
              AND existing.version_label = seed.version_label
        );
        """)
    for evidence in _evidence_rows():
        op.execute(_insert_evidence_sql(**evidence))


def downgrade() -> None:
    """Remove seeded chatbot evidence records."""
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
            'answer-card-seed-2026-05-29'
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
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000001",
            "source_id": "cdc-public-health",
            "topic": "diabetes_plate_method",
            "claim_summary": "Diabetes meal planning can use a plate structure to moderate carbohydrates and add vegetables and protein.",
            "allowed_user_wording": "저녁 탄수화물은 한 번에 몰리지 않게 줄이고 채소와 단백질 반찬을 곁들인다.",
            "blocked_wording": "당뇨가 치료됩니다. 탄수화물을 완전히 끊으세요. 약을 조절하세요.",
            "applicability_note": "당뇨 맥락의 식사 조정 질문",
            "caution_level": "caution",
            "specific_examples": ("비전분 채소", "두부", "달걀", "생선구이", "콩류"),
            "checklist": ("밥·면·빵 양", "달콤한 간식", "다음 식사 구성", "혈당 기록 여부"),
            "caution_conditions": ("저혈당 증상", "약 복용 중인 경우", "증상이 악화되는 경우"),
            "must_not_say": ("당뇨가 치료됩니다", "탄수화물을 완전히 끊으세요", "약을 조절하세요"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000002",
            "source_id": "niddk-diabetes-living",
            "topic": "diabetes_healthy_living",
            "claim_summary": "Diabetes self-management combines meal planning, activity, weight, medication awareness, and glucose records.",
            "allowed_user_wording": "식사 계획, 신체활동, 수면, 체중 기록을 작은 행동으로 나눠 관리한다.",
            "blocked_wording": "혈당약을 바꾸세요. 검사수치만으로 치료를 결정하세요.",
            "applicability_note": "당뇨 생활관리 일반 질문",
            "caution_level": "caution",
            "specific_examples": ("걷기", "식사 기록", "수면 기록", "체중 기록"),
            "checklist": ("식사 시간", "활동량", "수면 시간", "체중 변화", "약 복용 여부"),
            "caution_conditions": ("검사수치 해석", "처방 변경", "저혈당 의심 증상"),
            "must_not_say": ("혈당약을 바꾸세요", "검사수치만으로 치료를 결정하세요"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000003",
            "source_id": "cdc-public-health",
            "topic": "adult_activity",
            "claim_summary": "Adults can use walking and strength activity as general health-management activity targets.",
            "allowed_user_wording": "걷기부터 시작하고 강도와 시간을 기록한다.",
            "blocked_wording": "통증이 있어도 계속하세요. 약을 줄이고 운동하세요.",
            "applicability_note": "일반 운동 관리 질문",
            "caution_level": "info",
            "specific_examples": ("걷기", "자전거", "가벼운 근력운동"),
            "checklist": ("운동 시간", "강도", "어지러움", "숨참", "통증"),
            "caution_conditions": ("가슴 통증", "숨참", "실신", "마비"),
            "must_not_say": ("통증이 있어도 계속하세요", "약을 줄이고 운동하세요"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000004",
            "source_id": "cdc-public-health",
            "topic": "adult_sleep",
            "claim_summary": "Adult sleep tracking can be reviewed with meal, caffeine, and activity patterns.",
            "allowed_user_wording": "수면 시간을 기록하고 식사·카페인·활동 패턴과 함께 본다.",
            "blocked_wording": "수면제를 복용하세요. 진단명입니다.",
            "applicability_note": "일반 수면 관리 질문",
            "caution_level": "info",
            "specific_examples": ("취침 시간", "기상 시간", "카페인", "야식"),
            "checklist": ("수면 시간", "낮 졸림", "카페인 섭취", "야식 여부"),
            "caution_conditions": ("심한 불면", "호흡 문제", "정신건강 위험"),
            "must_not_say": ("수면제를 복용하세요", "진단명입니다"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000005",
            "source_id": "cdc-public-health",
            "topic": "exercise_dizziness",
            "claim_summary": "Dizziness during or after exercise should prompt stopping activity, rest, hydration, cooling, and symptom monitoring.",
            "allowed_user_wording": "운동을 멈추고 휴식, 수분 보충, 서늘한 장소 이동을 우선한다.",
            "blocked_wording": "계속 운동하세요. 원인은 이것입니다.",
            "applicability_note": "응급 red flag가 없는 운동 후 어지러움",
            "caution_level": "caution",
            "specific_examples": ("휴식", "수분 보충", "서늘한 곳", "증상 기록"),
            "checklist": ("어지러움", "탈수 가능성", "식사 간격", "운동 강도"),
            "caution_conditions": ("가슴 통증", "숨참", "실신", "마비", "증상 악화"),
            "must_not_say": ("계속 운동하세요", "원인은 이것입니다"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000006",
            "source_id": "kdris-2025",
            "topic": "sodium_dinner_adjustment",
            "claim_summary": "Lower-sodium dinner changes start with broth, sauces, salty preserved foods, and processed meats.",
            "allowed_user_wording": "찌개나 라면은 국물을 남기고 소스와 장류는 부어 먹기보다 찍어 먹는다.",
            "blocked_wording": "라면은 절대 먹지 마세요. 채소와 단백질을 드세요.",
            "applicability_note": "나트륨 저녁 식사 조정 질문",
            "caution_level": "info",
            "specific_examples": (
                "오이",
                "양배추",
                "브로콜리",
                "버섯",
                "토마토",
                "시금치",
                "두부",
                "달걀",
                "생선구이",
                "닭가슴살",
                "살코기",
                "콩류",
            ),
            "checklist": ("국물", "소스", "장류", "가공육", "김치류", "짠 반찬"),
            "caution_conditions": ("신장질환", "칼륨 제한", "심부전", "부종"),
            "must_not_say": ("라면은 절대 먹지 마세요", "채소와 단백질을 드세요"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000007",
            "source_id": "kdca-healthinfo",
            "topic": "hypertension_meal_adjustment",
            "claim_summary": "Hypertension meal context should focus on reducing salty broth, sauces, and processed foods without changing medication.",
            "allowed_user_wording": "짠 국물과 가공식품을 줄이고 다음 끼니에서 덜 짠 반찬을 고른다.",
            "blocked_wording": "혈압약을 줄이세요. 고혈압입니다. 안전합니다.",
            "applicability_note": "고혈압 맥락의 식사 조정 질문",
            "caution_level": "caution",
            "specific_examples": ("국물 남기기", "소스 찍어 먹기", "두부", "생선구이", "채소 반찬"),
            "checklist": ("짠 국물", "장류", "가공식품", "혈압약 복용 여부", "혈압 기록"),
            "caution_conditions": ("어지러움", "흉통", "숨참", "약 변경 질문"),
            "must_not_say": ("혈압약을 줄이세요", "고혈압입니다", "안전합니다"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000008",
            "source_id": "niddk-kidney-disease",
            "topic": "kidney_disease_meal_caution",
            "claim_summary": "Kidney disease meal context should reduce sodium while checking potassium restriction before broad fruit or vegetable advice.",
            "allowed_user_wording": "칼륨 제한을 들은 적이 있으면 채소와 과일 선택은 별도 확인이 필요하다.",
            "blocked_wording": "칼륨 많은 식품을 마음껏 드세요. 신장질환입니다.",
            "applicability_note": "신장질환 맥락의 식사 조정 질문",
            "caution_level": "caution",
            "specific_examples": ("국물 남기기", "가공육 줄이기", "채소 선택 확인", "식사 기록"),
            "checklist": ("신장질환", "칼륨 제한", "나트륨", "단백질", "검사 결과"),
            "caution_conditions": ("칼륨 제한", "부종", "검사수치 해석", "처방 변경"),
            "must_not_say": ("칼륨 많은 식품을 마음껏 드세요", "신장질환입니다"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000009",
            "source_id": "nih-ods-magnesium",
            "topic": "magnesium_supplement_caution",
            "claim_summary": "Magnesium supplement questions should check label amount, medication type, kidney function, and symptoms.",
            "allowed_user_wording": "마그네슘의 일반 역할과 식품 후보를 설명하고 제품 라벨 확인을 안내한다.",
            "blocked_wording": "먹어도 됩니다. 안전합니다. 먹으면 안 됩니다. 복용량을 바꾸세요.",
            "applicability_note": "혈압약 등 복약 맥락의 마그네슘 보충제 질문",
            "caution_level": "professional_review",
            "specific_examples": ("견과류", "콩류", "통곡물", "녹색 잎채소"),
            "checklist": (
                "제품 라벨",
                "함량",
                "혈압약 종류",
                "신장 기능",
                "어지러움",
                "설사",
                "복통",
            ),
            "caution_conditions": ("혈압약 복용", "신장 기능 저하", "이상 증상", "새 보충제 시작"),
            "must_not_say": (
                "먹어도 됩니다",
                "안전합니다",
                "먹으면 안 됩니다",
                "복용량을 바꾸세요",
            ),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000010",
            "source_id": "kdris-2025",
            "topic": "vitamin_d_food_candidates",
            "claim_summary": "Vitamin D food discussion should focus on food candidates and label checks, not high-dose decisions.",
            "allowed_user_wording": "식품 후보와 기록 확인을 우선하고 보충제 용량 결정은 하지 않는다.",
            "blocked_wording": "고용량을 드세요. 검사수치를 치료하세요.",
            "applicability_note": "비타민 D 식품 후보 질문",
            "caution_level": "info",
            "specific_examples": ("생선", "달걀", "강화식품"),
            "checklist": ("식사 기록", "보충제 라벨", "중복 섭취"),
            "caution_conditions": ("검사수치 해석", "고용량 보충제", "처방 변경"),
            "must_not_say": ("고용량을 드세요", "검사수치를 치료하세요"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000011",
            "source_id": "kdris-2025",
            "topic": "protein_food_candidates",
            "claim_summary": "Protein food guidance should use concrete lower-salt protein foods and avoid overgeneralization.",
            "allowed_user_wording": "한 끼에서 덜 짠 단백질 반찬 후보를 고르게 한다.",
            "blocked_wording": "단백질을 무조건 많이 드세요. 가공육도 괜찮습니다.",
            "applicability_note": "단백질 식사 후보 질문",
            "caution_level": "info",
            "specific_examples": ("두부", "달걀", "생선구이", "닭가슴살", "살코기", "콩류"),
            "checklist": ("단백질 반찬", "가공육 여부", "조리 간"),
            "caution_conditions": ("신장질환", "단백질 제한", "알레르기"),
            "must_not_say": ("단백질을 무조건 많이 드세요", "가공육도 괜찮습니다"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000012",
            "source_id": "kdris-2025",
            "topic": "fiber_food_candidates",
            "claim_summary": "Fiber food guidance should use vegetables, legumes, and whole grains as concrete meal candidates.",
            "allowed_user_wording": "채소, 콩류, 통곡물 후보를 식사 조정 예시로 든다.",
            "blocked_wording": "칼륨 제한과 무관하게 많이 드세요.",
            "applicability_note": "식이섬유 식사 후보 질문",
            "caution_level": "info",
            "specific_examples": ("양배추", "브로콜리", "콩류", "통곡물", "버섯"),
            "checklist": ("채소 반찬", "콩류", "통곡물", "수분 섭취"),
            "caution_conditions": ("신장질환", "칼륨 제한", "소화 불편"),
            "must_not_say": ("칼륨 제한과 무관하게 많이 드세요",),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000013",
            "source_id": "kdca-healthinfo",
            "topic": "general_health_record_review",
            "claim_summary": "General health-management questions should review confirmed meals, supplements, activity, and sleep records first.",
            "allowed_user_wording": "확인된 기록을 먼저 보고 반복되는 식사, 영양제, 활동 패턴을 정리한다.",
            "blocked_wording": "진단입니다. 치료를 시작하세요. 약을 조절하세요.",
            "applicability_note": "일반 건강관리 기록 검토 질문",
            "caution_level": "info",
            "specific_examples": ("식사 기록", "영양제 라벨", "활동 기록", "수면 기록"),
            "checklist": ("확정된 기록", "반복 패턴", "새 증상", "복용 중인 약"),
            "caution_conditions": ("응급 증상", "검사수치 판단", "복약 변경", "증상 악화"),
            "must_not_say": ("진단입니다", "치료를 시작하세요", "약을 조절하세요"),
        },
        {
            "evidence_id": "aaaaaaaa-0001-4000-8000-000000000014",
            "source_id": "mfds-drug-safety",
            "topic": "supplement_label_check",
            "claim_summary": "Supplement questions should start with label serving size, ingredients, functional claims, duplication, and medication context.",
            "allowed_user_wording": "제품 라벨의 섭취량, 원재료, 기능성 표시 범위를 확인한다.",
            "blocked_wording": "이 제품을 구매하세요. 누구에게나 안전합니다. 약 대신 드세요.",
            "applicability_note": "일반 영양제 라벨 확인 질문",
            "caution_level": "caution",
            "specific_examples": ("제품 라벨", "섭취량", "원재료", "기능성 표시 범위"),
            "checklist": ("제품 라벨", "섭취량", "원재료", "성분 중복", "복용 중인 약"),
            "caution_conditions": ("복약 중", "질환 치료 중", "임신", "이상 증상"),
            "must_not_say": ("이 제품을 구매하세요", "누구에게나 안전합니다", "약 대신 드세요"),
        },
    )
