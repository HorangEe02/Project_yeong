"""Integration: FORCE RLS owner isolation under the ``lemon_app`` request role.

Stage-2 전제 검증(권위: outputs/todo-list/2026-06-13/2026-06-13-rls-activation-rollout.md §4).
0023a(역할)+0023b(정책)+0023c(FORCE) 설계가 **실제 적용된 테이블**에서 소유자 격리를
end-to-end로 강제하는지 확인한다 — 롤아웃 문서가 "Stage-2 최대 리스크 제거"로 규정한 테스트.

단위 테스트(tests/unit/db/test_rls_context.py)는 fake 세션이라 GUC가 설정되는지만 보고
정책 강제는 검증하지 못한다. 이 테스트는 **비-superuser ``lemon_app`` 접속**으로
정책+FORCE가 실제로 행을 막는지 본다(superuser 접속은 RLS를 우회하므로 의미 없음).

실행 게이트(둘 다 설정해야 실행, 아니면 skip):
  TEST_DATABASE_URL          — 시드/정리/메타데이터용 관리 접속(마이그레이션 적용된 DB)
  TEST_RLS_APP_DATABASE_URL  — ``lemon_app``(NOSUPERUSER·NOBYPASSRLS) 접속(RLS 컨텍스트)

로컬 실행 예(supabase_db, lemon_app 로컬 비밀번호 설정 후):
  TEST_DATABASE_URL=postgresql+asyncpg://postgres:***@127.0.0.1:56322/postgres \
  TEST_RLS_APP_DATABASE_URL=postgresql+asyncpg://lemon_app:***@127.0.0.1:56322/postgres \
  .venv/bin/python -m pytest Nutrition-backend/tests/integration/db/test_rls_owner_isolation.py -q

대표 테이블로 plaintext-owner 아카이타입(Type A) ``analysis_results``를 쓴다. hashed-owner(B)
/child(C)는 동일 정책 메커니즘으로 0023b가 생성하며 force_rls_poc.sql이 4종 전부 증명했다 —
여기서는 실제 적용 정책이 대표 테이블에서 격리·fail-closed·catalog-read·WITH CHECK를
만족하는지에 집중한다.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the live FORCE RLS owner-isolation integration test."
    ),
)

# Type A archetype: plaintext owner_subject keyed on app.current_subject GUC.
_OWNER_TABLE = "analysis_results"
# Catalog archetype: public read for the request role, no owner filter.
_CATALOG_TABLE = "supplement_products"

_INSERT = text(
    f"INSERT INTO {_OWNER_TABLE} "
    "(id, owner_subject, analysis_type, algorithm_version, input_snapshot, result_snapshot) "
    "VALUES (gen_random_uuid(), :owner, 'nutrition_analysis', :alg, '{}'::jsonb, '{}'::jsonb)"
)


async def _set_subject(conn: AsyncConnection, subject: str) -> None:
    """Set the transaction-local owner-subject GUC the 0023b policies read."""
    await conn.execute(text("SELECT set_config('app.current_subject', :s, true)"), {"s": subject})


async def _owners_seen(conn: AsyncConnection, alg: str) -> set[str]:
    """Owner subjects visible for this test's marker rows under the current GUC."""
    result = await conn.execute(
        text(f"SELECT owner_subject FROM {_OWNER_TABLE} WHERE algorithm_version = :alg"),
        {"alg": alg},
    )
    return {row[0] for row in result}


async def test_force_rls_isolates_owners_under_lemon_app_role() -> None:
    """Verify role+GUC+policy+FORCE isolate owners end-to-end on a real table.

    Asserts, against the live applied schema, that the ``lemon_app`` role:
      * is non-superuser and non-bypassrls (the precondition for RLS to bite),
      * the owner table has ROW LEVEL SECURITY enabled AND forced,
      * sees only its own rows per ``app.current_subject`` (cross-owner isolation),
      * sees zero rows when the subject GUC is empty (fail-closed, not a leak),
      * cannot INSERT a row owned by another subject (WITH CHECK),
      * can still read the catalog table unfiltered regardless of subject.
    """
    assert ADMIN_URL is not None and APP_URL is not None
    alg = f"rls-iso-{uuid.uuid4()}"
    owner_a = f"test-iss::alice-{uuid.uuid4()}"
    owner_b = f"test-iss::bob-{uuid.uuid4()}"

    admin = None
    app = None
    try:
        admin = create_async_engine(ADMIN_URL, pool_pre_ping=True)
        app = create_async_engine(APP_URL, pool_pre_ping=True)
        # ── seed two owners' rows via the admin connection ──
        async with admin.begin() as conn:
            await conn.execute(_INSERT, {"owner": owner_a, "alg": alg})
            await conn.execute(_INSERT, {"owner": owner_b, "alg": alg})

        # ── precondition: request role is non-privileged ──
        async with app.connect() as conn:
            role_super, role_bypass = (
                await conn.execute(
                    text(
                        "SELECT rolsuper, rolbypassrls FROM pg_roles "
                        "WHERE rolname = current_user"
                    )
                )
            ).one()
            assert role_super is False, "request role must not be a superuser"
            assert role_bypass is False, "request role must not have BYPASSRLS"

        # ── precondition: owner table has RLS enabled AND forced ──
        async with admin.connect() as conn:
            enabled, forced = (
                await conn.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                        f"WHERE oid = 'public.{_OWNER_TABLE}'::regclass"
                    )
                )
            ).one()
            assert enabled is True, f"{_OWNER_TABLE} must have ROW LEVEL SECURITY enabled"
            assert forced is True, f"{_OWNER_TABLE} must have FORCE ROW LEVEL SECURITY"

        # ── isolation: each subject sees only its own row ──
        async with app.begin() as conn:
            await _set_subject(conn, owner_a)
            assert await _owners_seen(conn, alg) == {owner_a}

        async with app.begin() as conn:
            await _set_subject(conn, owner_b)
            assert await _owners_seen(conn, alg) == {owner_b}

        # ── fail-closed: empty subject sees nothing (never a leak) ──
        async with app.begin() as conn:
            await _set_subject(conn, "")
            assert await _owners_seen(conn, alg) == set()

        # ── WITH CHECK: a subject cannot insert a row owned by another ──
        # Pin the failure to the RLS policy violation (SQLSTATE 42501) so a NOT
        # NULL/FK/network error cannot masquerade as the policy working.
        with pytest.raises(DBAPIError) as exc_info:
            async with app.begin() as conn:
                await _set_subject(conn, owner_a)
                await conn.execute(_INSERT, {"owner": owner_b, "alg": alg})
        orig = getattr(exc_info.value, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
        assert sqlstate == "42501", f"expected RLS policy violation 42501, got {sqlstate!r}"

        # ── catalog: readable and unfiltered even with no subject set ──
        # Owner tables return 0 rows under an empty subject (asserted above), so a
        # non-empty catalog read here proves catalog_read is NOT owner-filtered.
        # Counting only on the app connection avoids a cross-connection count race.
        async with app.begin() as conn:
            await _set_subject(conn, "")
            app_catalog_count = (
                await conn.execute(text(f"SELECT count(*) FROM {_CATALOG_TABLE}"))
            ).scalar_one()
        assert app_catalog_count >= 1
    finally:
        if admin is not None:
            async with admin.begin() as conn:
                await conn.execute(
                    text(f"DELETE FROM {_OWNER_TABLE} WHERE algorithm_version = :alg"),
                    {"alg": alg},
                )
        if app is not None:
            await app.dispose()
        if admin is not None:
            await admin.dispose()
