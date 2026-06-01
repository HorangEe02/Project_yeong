"""Compliance D module tables — SQLite compliance.db → PostgreSQL.

Revision ID: 20260527_0004
Revises: 20260526_0003
Create Date: 2026-05-27

Postmortem 2026-05-27 후속 — D 모듈 SQLite 단일 장애점 해소.

이관 대상 테이블 8개 (현재 ajin-ai-assistant-react/data/compliance.db):
- crawl_history    : 크롤링 스냅샷 (언제 무엇을 어디서 받았는가)
- regulations      : 외부 9 소스에서 수집된 규제 마스터
- crawl_runs       : 실행 단위 감사 (F12, 본 incident 의 직접 원인 테이블)
- http_cache       : ETag / Last-Modified 캐시
- draft_user_prefs : Module B 사용자 prefs 서버 sync
- draft_dept_usage : draft history 부서 aggregation
- draft_user_picks : 사용자별 doc_type 선호
- draft_agg_runs   : aggregation 작업 감사

본 migration 은 schema 만 생성한다. 데이터 이관은 별도 스크립트
(`scripts/migrate_compliance_db_to_postgres.py`, Phase 2).

PostgreSQL 에서는 자동 RLS enable (Supabase data-api 노출 차단).
SQLite 환경에서는 ENABLE ROW LEVEL SECURITY 가 skip 된다.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260527_0004"
down_revision = "20260526_0003"
branch_labels = None
depends_on = None


def _now_col() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def _enable_rls(*tables: str) -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    for table in tables:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))


def upgrade() -> None:
    """Create the D module compliance schema on PostgreSQL."""

    # ── crawl_history — 크롤링 스냅샷 ───────────────────────────────────────
    op.create_table(
        "crawl_history",
        sa.Column("crawl_id", sa.Integer, primary_key=True),
        sa.Column("crawler_name", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False, server_default=""),
        sa.Column("json_filename", sa.String(255), nullable=False),
        sa.Column("crawled_at", sa.String(40), nullable=False),
        sa.Column("total_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("errors", sa.Text, nullable=False, server_default=""),
        _now_col(),
    )
    op.create_index("idx_crawl_history_name", "crawl_history", ["crawler_name"])

    # ── regulations — 외부 9 소스 규제 마스터 ─────────────────────────────
    op.create_table(
        "regulations",
        sa.Column("reg_pk", sa.Integer, primary_key=True),
        sa.Column(
            "crawl_id",
            sa.Integer,
            sa.ForeignKey("crawl_history.crawl_id"),
            nullable=False,
        ),
        sa.Column("reg_id", sa.String(255), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("name_ko", sa.Text, nullable=False, server_default=""),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("category", sa.String(80), nullable=False, server_default=""),
        sa.Column("authority", sa.String(160), nullable=False, server_default=""),
        sa.Column("compliance_status", sa.String(40), nullable=False, server_default=""),
        sa.Column("effective_date", sa.String(40), nullable=False, server_default=""),
        sa.Column("last_amended", sa.String(40), nullable=False, server_default=""),
        sa.Column("content_json", sa.Text, nullable=False, server_default="{}"),
        _now_col(),
    )
    op.create_index("idx_reg_doc_type", "regulations", ["doc_type"])
    op.create_index("idx_reg_crawl_id", "regulations", ["crawl_id"])
    op.create_index("idx_reg_status", "regulations", ["compliance_status"])

    # ── crawl_runs — 실행 단위 감사 (F12, incident 원인 테이블) ───────────
    op.create_table(
        "crawl_runs",
        sa.Column("run_id", sa.Integer, primary_key=True),
        sa.Column("crawler_name", sa.String(80), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("elapsed_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ok", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updates_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors", sa.Text, nullable=False, server_default=""),
        sa.Column("trigger_source", sa.String(40), nullable=False, server_default=""),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("http_etag", sa.String(255), nullable=False, server_default=""),
        sa.Column("http_last_modified", sa.String(255), nullable=False, server_default=""),
        sa.Column("user_id", sa.String(80), nullable=False, server_default=""),
    )
    op.create_index("idx_crawl_runs_name", "crawl_runs", ["crawler_name"])
    op.create_index("idx_crawl_runs_started", "crawl_runs", ["started_at"])
    op.create_index("idx_crawl_runs_ok", "crawl_runs", ["ok"])

    # ── http_cache — ETag / Last-Modified ─────────────────────────────────
    op.create_table(
        "http_cache",
        sa.Column("url", sa.Text, primary_key=True),
        sa.Column("etag", sa.String(255), nullable=False, server_default=""),
        sa.Column("last_modified", sa.String(255), nullable=False, server_default=""),
        sa.Column("fetched_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("http_status", sa.Integer, nullable=False, server_default="0"),
        sa.Column("body_sha256", sa.String(64), nullable=False, server_default=""),
        sa.Column("hit_count", sa.Integer, nullable=False, server_default="0"),
    )

    # ── draft_user_prefs — Module B 사용자 prefs ──────────────────────────
    op.create_table(
        "draft_user_prefs",
        sa.Column("user_id", sa.String(80), primary_key=True),
        sa.Column(
            "favorited_doc_types",
            sa.Text,
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # ── draft_dept_usage — 부서별 doc_type 사용 빈도 ──────────────────────
    op.create_table(
        "draft_dept_usage",
        sa.Column("department", sa.String(160), nullable=False),
        sa.Column("doc_type_id", sa.String(80), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_aggregated_at", sa.String(40), nullable=True),
        sa.PrimaryKeyConstraint("department", "doc_type_id"),
    )
    op.create_index("idx_dept_usage_dept", "draft_dept_usage", ["department"])

    # ── draft_user_picks — 사용자별 doc_type 선호 ─────────────────────────
    op.create_table(
        "draft_user_picks",
        sa.Column("user_id", sa.String(80), nullable=False),
        sa.Column("doc_type_id", sa.String(80), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_picked_at", sa.String(40), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "doc_type_id"),
    )
    op.create_index("idx_user_picks_user", "draft_user_picks", ["user_id"])

    # ── draft_agg_runs — aggregation 작업 감사 ────────────────────────────
    op.create_table(
        "draft_agg_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("ended_at", sa.String(40), nullable=True),
        sa.Column("ok", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("dept_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("user_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=False, server_default=""),
    )

    _enable_rls(
        "crawl_history",
        "regulations",
        "crawl_runs",
        "http_cache",
        "draft_user_prefs",
        "draft_dept_usage",
        "draft_user_picks",
        "draft_agg_runs",
    )


def downgrade() -> None:
    """Drop the D module compliance schema."""
    for table in (
        "draft_agg_runs",
        "draft_user_picks",
        "draft_dept_usage",
        "draft_user_prefs",
        "http_cache",
        "crawl_runs",
        "regulations",
        "crawl_history",
    ):
        op.drop_table(table)
