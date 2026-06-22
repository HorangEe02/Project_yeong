"""Seed lithium supplement interaction boundary.

Revision ID: 0039_seed_lithium_supplement_boundary
Revises: 0038_create_food_records
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0039_seed_lithium_supplement_boundary"
down_revision: str | Sequence[str] | None = "0038_create_food_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed reviewed source/version metadata and the no-LLM boundary row."""
    op.execute("""
        INSERT INTO medical_sources (
            id, source_family, publisher, title, canonical_url, jurisdiction,
            source_type, default_review_status, owner
        )
        VALUES (
            'medlineplus-lithium',
            'drug_safety_boundary',
            'U.S. National Library of Medicine',
            'MedlinePlus Lithium Drug Information',
            'https://medlineplus.gov/druginfo/meds/a681039.html',
            'US',
            'public_health',
            'reviewed',
            'AI Agent medical knowledge review'
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
        SELECT
            '88888888-8888-4888-8888-888888888888'::uuid,
            'medlineplus-lithium',
            '2026-05 MVP source registry',
            NULL::date,
            '2026-05-31'::date,
            '2026-11-30'::date,
            'reviewed',
            'AI Agent medical knowledge review',
            'Seeded for lithium plus supplement professional-review boundary.'
        WHERE NOT EXISTS (
            SELECT 1
            FROM medical_source_versions
            WHERE source_id = 'medlineplus-lithium'
              AND version_label = '2026-05 MVP source registry'
        );
        """)
    op.execute("""
        INSERT INTO medical_policy_boundaries (
            id, boundary_code, topic, trigger_intent, response_status,
            required_warning_code, allowed_response_pattern,
            blocked_response_pattern, source_version_id, review_status
        )
        SELECT
            'bbbbbbbb-0001-4000-8000-000000000007'::uuid,
            'p0_lithium_selenium_supplement',
            'lithium_selenium_supplement_interaction',
            'drug_or_interaction',
            'professional_review',
            'Drug interaction boundary applied',
            '리튬의 혈중 농도, 신장 기능, 탈수·염분 변화, 동반 약과 영양제 확인 필요성을 설명하고, 개인 병용 가능 여부를 단정하지 않으며, 제품 라벨과 복용 목적을 의사 또는 약사에게 확인하도록 안내한다.',
            '먹어도 됩니다; 안전합니다; 먹으면 안 됩니다; 처방을 바꾸세요; 리튬 용량을 조절하세요; 셀레늄 병용 가능 여부를 단정',
            (
                SELECT id
                FROM medical_source_versions
                WHERE source_id = 'medlineplus-lithium'
                  AND review_status = 'reviewed'
                  AND expires_at >= CURRENT_DATE
                ORDER BY reviewed_at DESC
                LIMIT 1
            ),
            'reviewed'
        WHERE NOT EXISTS (
            SELECT 1
            FROM medical_policy_boundaries
            WHERE boundary_code = 'p0_lithium_selenium_supplement'
              AND review_status = 'reviewed'
        );
        """)


def downgrade() -> None:
    """Remove the lithium supplement boundary seed."""
    op.execute("""
        DELETE FROM medical_policy_boundaries
        WHERE boundary_code = 'p0_lithium_selenium_supplement';
        """)
    op.execute("""
        DELETE FROM medical_source_versions
        WHERE source_id = 'medlineplus-lithium'
          AND version_label = '2026-05 MVP source registry';
        """)
    op.execute("""
        DELETE FROM medical_sources
        WHERE id = 'medlineplus-lithium';
        """)
