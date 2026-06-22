"""Regression: chat-approved app health snapshots must not shadow pipeline rows.

store_app_health_analysis_result()가 같은 analysis_type='nutrition_analysis'에
{analysis_kind, snapshot} 형식을 영속하므로, 최신 행 조회가 형식 필터 없이
created_at만 보면 챗 승인 직후 대시보드/진단/보충제 프리뷰가 422로 깨진다
(2026-06-12 iOS 26.5 워크스루에서 발견).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.models.db.analysis_result import AnalysisResult
from src.security.auth import AuthenticatedUser
from src.services.nutrition_diagnosis import get_latest_nutrition_analysis_result

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="Set TEST_DATABASE_URL to run live database integration tests.",
)


async def test_latest_nutrition_query_skips_chat_snapshot_rows() -> None:
    """Verify the latest-nutrition query returns the pipeline row, not a newer chat snapshot."""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    user = AuthenticatedUser(
        subject=f"shape-filter-regression-{uuid.uuid4()}", issuer="test-issuer"
    )
    owner = f"{user.issuer}::{user.subject}"
    base_time = datetime.now(UTC)

    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session:
            pipeline_row = AnalysisResult(
                owner_subject=owner,
                analysis_type="nutrition_analysis",
                algorithm_version="nutrition-analysis-regression",
                input_snapshot={},
                result_snapshot={"results": []},
                created_at=base_time - timedelta(minutes=1),
            )
            chat_row = AnalysisResult(
                owner_subject=owner,
                analysis_type="nutrition_analysis",
                algorithm_version="app-health-analysis-v1.0.0",
                input_snapshot={"user_confirmed": True},
                result_snapshot={"analysis_kind": "today_analysis", "snapshot": {}},
                created_at=base_time,
            )
            session.add_all([pipeline_row, chat_row])
            await session.commit()

            latest = await get_latest_nutrition_analysis_result(session, user)
            assert latest is not None
            assert latest.id == pipeline_row.id

        async with sessionmaker() as session:
            await session.execute(
                delete(AnalysisResult).where(AnalysisResult.owner_subject == owner)
            )
            await session.commit()
    finally:
        await engine.dispose()


async def test_latest_nutrition_query_returns_none_for_chat_only_owner() -> None:
    """Verify an owner with only chat snapshots gets None (dashboard renders not_ready, not 422)."""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    user = AuthenticatedUser(subject=f"chat-only-regression-{uuid.uuid4()}", issuer="test-issuer")
    owner = f"{user.issuer}::{user.subject}"

    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session:
            session.add(
                AnalysisResult(
                    owner_subject=owner,
                    analysis_type="nutrition_analysis",
                    algorithm_version="app-health-analysis-v1.0.0",
                    input_snapshot={"user_confirmed": True},
                    result_snapshot={"analysis_kind": "health_analysis", "snapshot": {}},
                )
            )
            await session.commit()

            latest = await get_latest_nutrition_analysis_result(session, user)
            assert latest is None

        async with sessionmaker() as session:
            await session.execute(
                delete(AnalysisResult).where(AnalysisResult.owner_subject == owner)
            )
            await session.commit()
    finally:
        await engine.dispose()
