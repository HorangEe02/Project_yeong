"""SQLAlchemy ORM 모델 단위 테스트 — DB 연결 없이 mapper / 구조 검증.

실 Postgres CRUD 는 ``tests/integration/db/test_models.py`` 에서 testcontainers 로
검증한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 10
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.models.db.audit import AccessAuditLog
from src.models.db.base import Base
from src.models.db.consent import ALLOWED_CONSENT_TYPES, ConsentRecord
from src.models.db.supplement import Supplement
from src.models.db.user import User, UserProfile


class TestMetadataRegistration:
    def test_all_five_tables_registered(self) -> None:
        expected = {
            "users",
            "user_profiles",
            "consent_records",
            "access_audit_logs",
            "supplements",
        }
        assert expected.issubset(set(Base.metadata.tables.keys()))


class TestUserColumns:
    def test_required_columns(self) -> None:
        cols = {c.name for c in User.__table__.columns}
        assert {"id", "email", "password_hash", "created_at", "deleted_at"}.issubset(cols)

    def test_email_unique_and_indexed(self) -> None:
        email_col = User.__table__.columns["email"]
        assert email_col.unique is True
        assert email_col.index is True

    def test_relationships(self) -> None:
        rels = User.__mapper__.relationships
        assert "profile" in rels
        assert "consents" in rels
        assert "supplements" in rels

    def test_instantiation_no_db(self) -> None:
        user = User(
            id=uuid.uuid4(),
            email="t@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        assert user.email == "t@example.com"


class TestUserProfileColumns:
    def test_fk_user_id_cascade(self) -> None:
        fks = list(UserProfile.__table__.columns["user_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "users"
        assert fks[0].ondelete == "CASCADE"

    def test_chronic_diseases_and_medications_present(self) -> None:
        cols = {c.name for c in UserProfile.__table__.columns}
        assert "chronic_diseases" in cols
        assert "medications" in cols


class TestConsentRecord:
    def test_required_columns(self) -> None:
        cols = {c.name for c in ConsentRecord.__table__.columns}
        expected = {
            "id",
            "user_id",
            "consent_type",
            "purpose",
            "data_categories",
            "retention_period_days",
            "policy_version",
            "accepted_at",
            "revoked_at",
        }
        assert expected.issubset(cols)

    def test_user_id_indexed(self) -> None:
        idx_columns = {
            tuple(c.name for c in idx.columns) for idx in ConsentRecord.__table__.indexes
        }
        assert ("user_id",) in idx_columns

    def test_allowed_consent_types_match_literal(self) -> None:
        expected = {
            "service_terms",
            "general_profile",
            "chronic_disease",
            "medications",
            "biometric",
            "image_history",
            "image_training",
            "image_partner",
        }
        assert frozenset(expected) == ALLOWED_CONSENT_TYPES


class TestAccessAuditLog:
    def test_no_raw_ip_column(self) -> None:
        """S6 / docs/10 §5 — raw IP 절대 컬럼화 X. hash 만 존재."""
        cols = {c.name for c in AccessAuditLog.__table__.columns}
        assert "ip_address" not in cols
        assert "ip_address_hash" in cols

    def test_required_columns(self) -> None:
        cols = {c.name for c in AccessAuditLog.__table__.columns}
        expected = {
            "id",
            "actor_user_id",
            "action",
            "resource_type",
            "resource_id",
            "ip_address_hash",
            "user_agent",
            "success",
            "error_code",
            "occurred_at",
        }
        assert expected.issubset(cols)

    def test_occurred_at_indexed(self) -> None:
        idx_columns = {
            tuple(c.name for c in idx.columns) for idx in AccessAuditLog.__table__.indexes
        }
        assert ("occurred_at",) in idx_columns


class TestSupplement:
    def test_required_columns(self) -> None:
        cols = {c.name for c in Supplement.__table__.columns}
        expected = {
            "id",
            "user_id",
            "product_name",
            "manufacturer",
            "ingredients",
            "ocr_engine",
            "llm_engine",
            "image_hash",
            "registered_at",
        }
        assert expected.issubset(cols)

    def test_no_raw_image_column(self) -> None:
        """docs/14 §3: 원본 이미지 저장 금지. hash만 보존."""
        cols = {c.name for c in Supplement.__table__.columns}
        assert "image_bytes" not in cols
        assert "image_data" not in cols
        assert "image_hash" in cols

    def test_fk_user_id_cascade(self) -> None:
        fks = list(Supplement.__table__.columns["user_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].ondelete == "CASCADE"
