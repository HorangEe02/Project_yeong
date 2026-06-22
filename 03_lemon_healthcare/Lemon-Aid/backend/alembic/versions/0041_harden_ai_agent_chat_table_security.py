"""Harden AI-agent chat tables to the fail-closed FORCE RLS posture.

Revision ID: 0041_harden_ai_agent_chat_table_security
Revises: 0040_extend_unknown_backlog_status_lifecycle
Create Date: 2026-06-10

The chat migrations 0030-0040 were rebased from a sibling branch that predates
this repo's FORCE RLS rollout (0023a/b/c, 0029), so their tables were created
without row-level security. This migration brings every chat table up to the
same posture as 0023b/0023c:

- owner-scoped tables get ``lemon_app`` policies keyed on the per-request GUCs
  (``app.current_subject`` / ``app.current_subject_hash``); unset GUC matches
  no rows -> fail-closed, never a leak.
- medical-source governance tables are curated knowledge (no per-user rows)
  and get the catalog read-only policy.
- ``chatbot_unknown_knowledge_events`` stores sanitized, ownerless backlog
  signals the service writes on unanswerable turns; it gets a service-level
  read/write policy (row isolation has no ownership dimension here).
- every table is REVOKEd from PUBLIC and the Supabase API roles, granted to
  ``lemon_app``, and FORCEd so even the table owner obeys the policies.
- the backlog summary view becomes ``security_invoker`` so it cannot bypass
  the events table policies once they exist.

No raw OCR text, provider payloads, or image bytes are involved.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0041_harden_ai_agent_chat_table_security"
down_revision: str | Sequence[str] | None = "0040_extend_unknown_backlog_status_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "lemon_app"
POLICY = "lemon_app_owner_rw"
CATALOG_POLICY = "lemon_app_catalog_read"
SERVICE_POLICY = "lemon_app_service_rw"

# Hashed owner_subject_hash column (0023b Type B).
HASHED_OWNER_TABLES = (
    "agent_memory",
    "agent_runs",
    "user_medications",
    "food_records",
)
# Plaintext owner_subject column (0023b Type A).
PLAINTEXT_OWNER_TABLES = ("reminder_preferences",)
# Curated reviewed-knowledge tables; request role reads, writes stay backend-only.
CATALOG_TABLES = (
    "medical_sources",
    "medical_source_versions",
    "medical_evidence_items",
    "medical_policy_boundaries",
    "medical_rag_chunks",
)
# Sanitized, ownerless service telemetry written by the chat backlog recorder.
SERVICE_RW_TABLES = ("chatbot_unknown_knowledge_events",)

ALL_TABLES = (
    *HASHED_OWNER_TABLES,
    *PLAINTEXT_OWNER_TABLES,
    *CATALOG_TABLES,
    *SERVICE_RW_TABLES,
)

BACKLOG_SUMMARY_VIEW = "chatbot_unknown_knowledge_backlog_summary"

_GUC_PLAINTEXT = "current_setting('app.current_subject', true)"
_GUC_HASH = "current_setting('app.current_subject_hash', true)"


def _revoke_api_roles(relation: str) -> None:
    """Revoke all privileges on a relation from the Supabase API roles if present."""
    op.execute(f"""
        DO $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE public.{relation} FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def upgrade() -> None:
    """Apply ENABLE+FORCE RLS, REVOKEs, lemon_app grants, and owner policies."""
    for table_name in ALL_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table_name} FROM PUBLIC")
        _revoke_api_roles(table_name)

    for table_name in (*HASHED_OWNER_TABLES, *PLAINTEXT_OWNER_TABLES, *SERVICE_RW_TABLES):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table_name} TO {APP_ROLE}")
    for table_name in CATALOG_TABLES:
        op.execute(f"GRANT SELECT ON public.{table_name} TO {APP_ROLE}")

    for table_name in HASHED_OWNER_TABLES:
        op.execute(f"""
            CREATE POLICY {POLICY} ON public.{table_name}
              FOR ALL TO {APP_ROLE}
              USING (owner_subject_hash = {_GUC_HASH})
              WITH CHECK (owner_subject_hash = {_GUC_HASH})
            """)
    for table_name in PLAINTEXT_OWNER_TABLES:
        op.execute(f"""
            CREATE POLICY {POLICY} ON public.{table_name}
              FOR ALL TO {APP_ROLE}
              USING (owner_subject = {_GUC_PLAINTEXT})
              WITH CHECK (owner_subject = {_GUC_PLAINTEXT})
            """)
    for table_name in CATALOG_TABLES:
        op.execute(f"""
            CREATE POLICY {CATALOG_POLICY} ON public.{table_name}
              FOR SELECT TO {APP_ROLE}
              USING (true)
            """)
    for table_name in SERVICE_RW_TABLES:
        op.execute(f"""
            CREATE POLICY {SERVICE_POLICY} ON public.{table_name}
              FOR ALL TO {APP_ROLE}
              USING (true)
              WITH CHECK (true)
            """)

    for table_name in ALL_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")

    op.execute(f"ALTER VIEW public.{BACKLOG_SUMMARY_VIEW} SET (security_invoker = on)")
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{BACKLOG_SUMMARY_VIEW} FROM PUBLIC")
    _revoke_api_roles(BACKLOG_SUMMARY_VIEW)
    op.execute(f"GRANT SELECT ON public.{BACKLOG_SUMMARY_VIEW} TO {APP_ROLE}")


def downgrade() -> None:
    """Drop the chat policies and restore the pre-hardening posture."""
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{BACKLOG_SUMMARY_VIEW} FROM {APP_ROLE}")
    op.execute(f"ALTER VIEW public.{BACKLOG_SUMMARY_VIEW} RESET (security_invoker)")

    for table_name in ALL_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} NO FORCE ROW LEVEL SECURITY")
    for table_name in (*HASHED_OWNER_TABLES, *PLAINTEXT_OWNER_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {POLICY} ON public.{table_name}")
    for table_name in CATALOG_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {CATALOG_POLICY} ON public.{table_name}")
    for table_name in SERVICE_RW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {SERVICE_POLICY} ON public.{table_name}")
    for table_name in ALL_TABLES:
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table_name} FROM {APP_ROLE}")
        op.execute(f"ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY")
