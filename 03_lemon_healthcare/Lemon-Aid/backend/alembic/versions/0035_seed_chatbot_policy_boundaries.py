"""Seed reviewed chatbot policy boundaries.

Revision ID: 0035_seed_chatbot_policy_boundaries
Revises: 0034_seed_chatbot_reviewed_evidence
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0035_seed_chatbot_policy_boundaries"
down_revision: str | None = "0034_seed_chatbot_reviewed_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed reviewed no-LLM P0 interaction boundaries."""
    for boundary in _boundary_rows():
        op.execute(_insert_boundary_sql(**boundary))


def downgrade() -> None:
    """Remove seeded chatbot policy boundaries."""
    codes = "', '".join(row["boundary_code"] for row in _boundary_rows())
    op.execute(f"""
        DELETE FROM medical_policy_boundaries
        WHERE boundary_code IN ('{codes}');
        """)


def _insert_boundary_sql(
    *,
    boundary_id: str,
    boundary_code: str,
    topic: str,
    allowed_response_pattern: str,
    blocked_response_pattern: str,
) -> str:
    return f"""
        INSERT INTO medical_policy_boundaries (
            id, boundary_code, topic, trigger_intent, response_status,
            required_warning_code, allowed_response_pattern,
            blocked_response_pattern, source_version_id, review_status
        )
        SELECT
            '{boundary_id}'::uuid,
            '{boundary_code}',
            '{topic}',
            'drug_or_interaction',
            'professional_review',
            'Drug interaction boundary applied',
            {allowed_response_pattern!r},
            {blocked_response_pattern!r},
            (
                SELECT id
                FROM medical_source_versions
                WHERE source_id = 'mfds-drug-safety'
                  AND review_status = 'reviewed'
                  AND expires_at >= CURRENT_DATE
                ORDER BY reviewed_at DESC
                LIMIT 1
            ),
            'reviewed'
        WHERE NOT EXISTS (
            SELECT 1
            FROM medical_policy_boundaries
            WHERE boundary_code = '{boundary_code}'
              AND review_status = 'reviewed'
        );
    """


def _boundary_rows() -> tuple[dict[str, str], ...]:
    allowed = (
        "위험 가능성의 이유를 설명하고, 개인 복용 가능 여부를 단정하지 않으며, "
        "약 이름, 성분명, 제품 라벨, 복용량, 질환, 증상, 처방 정보를 약사 또는 의사에게 "
        "확인하도록 안내한다."
    )
    blocked = (
        "먹어도 됩니다; 안전합니다; 먹으면 안 됩니다; 처방을 바꾸세요; "
        "용량을 늘리세요; 용량을 줄이세요; 개인 병용 가능 여부를 단정"
    )
    return (
        {
            "boundary_id": "bbbbbbbb-0001-4000-8000-000000000001",
            "boundary_code": "p0_st_johns_wort_antidepressant",
            "topic": "st_johns_wort_antidepressant_interaction",
            "allowed_response_pattern": allowed,
            "blocked_response_pattern": blocked,
        },
        {
            "boundary_id": "bbbbbbbb-0001-4000-8000-000000000002",
            "boundary_code": "p0_grapefruit_statin",
            "topic": "grapefruit_statin_interaction",
            "allowed_response_pattern": allowed,
            "blocked_response_pattern": blocked,
        },
        {
            "boundary_id": "bbbbbbbb-0001-4000-8000-000000000003",
            "boundary_code": "p0_potassium_salt_substitute",
            "topic": "potassium_salt_substitute_interaction",
            "allowed_response_pattern": allowed,
            "blocked_response_pattern": blocked,
        },
        {
            "boundary_id": "bbbbbbbb-0001-4000-8000-000000000004",
            "boundary_code": "p0_nitrate_pde5_inhibitor",
            "topic": "nitrate_pde5_inhibitor_interaction",
            "allowed_response_pattern": allowed,
            "blocked_response_pattern": blocked,
        },
        {
            "boundary_id": "bbbbbbbb-0001-4000-8000-000000000005",
            "boundary_code": "p0_serotonergic_supplement_antidepressant",
            "topic": "serotonergic_supplement_antidepressant_interaction",
            "allowed_response_pattern": allowed,
            "blocked_response_pattern": blocked,
        },
        {
            "boundary_id": "bbbbbbbb-0001-4000-8000-000000000006",
            "boundary_code": "p0_statin_red_yeast_rice",
            "topic": "statin_red_yeast_rice_interaction",
            "allowed_response_pattern": allowed,
            "blocked_response_pattern": blocked,
        },
    )
