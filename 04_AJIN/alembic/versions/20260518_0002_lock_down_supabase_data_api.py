"""Lock down Supabase Data API grants and RLS policies.

Revision ID: 20260518_0002
Revises: 20260518_0001
Create Date: 2026-05-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260518_0002"
down_revision = "20260518_0001"
branch_labels = None
depends_on = None

APP_TABLES = (
    "roles",
    "users",
    "login_history",
    "audit_logs",
    "employees",
    "employee_search_history",
    "regulation_changes",
    "crawl_history",
    "notification_outbox",
    "notification_logs",
    "live_alarms",
    "feedback_events",
    "draft_versions",
    "chat_messages",
    "attachments",
    "plc_violations",
)

DATA_API_ROLES = ("anon", "authenticated", "service_role")


def _quote_ident(value: str) -> str:
    """Return a safely quoted PostgreSQL identifier.

    Args:
        value: Identifier value.

    Returns:
        str: Quoted identifier.
    """

    return '"' + value.replace('"', '""') + '"'


def _postgres_only() -> bool:
    """Return whether the current Alembic dialect is PostgreSQL.

    Returns:
        bool: True when migration is running against PostgreSQL.
    """

    return op.get_context().dialect.name == "postgresql"


def _execute(sql: str) -> None:
    """Execute raw PostgreSQL SQL.

    Args:
        sql: SQL statement.
    """

    op.execute(sa.text(sql))


def _lock_existing_privileges() -> None:
    """Revoke Data API role access from existing public objects."""

    _execute(
        """
        do $$
        declare
          role_name text;
        begin
          foreach role_name in array array['anon', 'authenticated', 'service_role', 'public']
          loop
            if role_name = 'public' or exists (select 1 from pg_roles where rolname = role_name) then
              execute format('revoke all privileges on all tables in schema public from %I', role_name);
              execute format('revoke all privileges on all sequences in schema public from %I', role_name);
              execute format('revoke all privileges on all functions in schema public from %I', role_name);
              execute format('revoke usage on schema public from %I', role_name);
            end if;
          end loop;
        end
        $$;
        """
    )


def _lock_default_privileges() -> None:
    """Revoke future object grants for the migration owner."""

    _execute(
        """
        do $$
        declare
          role_name text;
        begin
          foreach role_name in array array['anon', 'authenticated', 'service_role']
          loop
            if exists (select 1 from pg_roles where rolname = role_name) then
              execute format(
                'alter default privileges in schema public revoke select, insert, update, delete on tables from %I',
                role_name
              );
              execute format(
                'alter default privileges in schema public revoke usage, select on sequences from %I',
                role_name
              );
              execute format(
                'alter default privileges in schema public revoke execute on functions from %I',
                role_name
              );
            end if;
          end loop;
          alter default privileges in schema public revoke execute on functions from public;
        end
        $$;
        """
    )


def _install_deny_policy(table: str) -> None:
    """Install a deny-all policy for public Data API roles.

    Args:
        table: Public table name.
    """

    table_literal = table.replace("'", "''")
    policy_name = f"deny_all_data_api_{table}"
    policy_literal = policy_name.replace("'", "''")
    _execute(
        f"""
        do $$
        begin
          if to_regclass('public.{table_literal}') is not null then
            execute format('alter table public.%I enable row level security', '{table_literal}');
            execute format('drop policy if exists %I on public.%I', '{policy_literal}', '{table_literal}');
            if exists (select 1 from pg_roles where rolname = 'anon')
               and exists (select 1 from pg_roles where rolname = 'authenticated') then
              execute format(
                'create policy %I on public.%I as restrictive for all to anon, authenticated using (false) with check (false)',
                '{policy_literal}',
                '{table_literal}'
              );
            end if;
          end if;
        end
        $$;
        """
    )


def upgrade() -> None:
    """Apply Data API deny-by-default posture for AJIN app tables."""

    if not _postgres_only():
        return
    _lock_existing_privileges()
    _lock_default_privileges()
    for table in APP_TABLES:
        _install_deny_policy(table)


def downgrade() -> None:
    """Remove explicit Data API deny policies.

    Grants are intentionally not restored because implicit public grants are not
    a safe rollback posture.
    """

    if not _postgres_only():
        return
    for table in APP_TABLES:
        table_literal = table.replace("'", "''")
        policy_literal = f"deny_all_data_api_{table}".replace("'", "''")
        _execute(
            f"""
            do $$
            begin
              if to_regclass('public.{table_literal}') is not null then
                execute format(
                  'drop policy if exists %I on public.%I',
                  '{policy_literal}',
                  '{table_literal}'
                );
              end if;
            end
            $$;
            """
        )
