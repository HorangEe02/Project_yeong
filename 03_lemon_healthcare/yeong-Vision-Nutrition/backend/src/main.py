"""FastAPI 앱 팩토리.

Phase 05 에서 ``auth`` / ``consents`` / ``supplements`` 라우터 + CORS + RequestId
middleware + DB lifespan 을 모두 묶는다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 5
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 12
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import RequestIdMiddleware
from src.api.v1 import auth as auth_router
from src.api.v1 import consents as consents_router
from src.api.v1 import supplements as supplements_router
from src.config import Settings, get_settings
from src.db.session import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 시작/종료 시 리소스 정리. DB engine 은 종료 시 dispose."""
    del app
    try:
        yield
    finally:
        await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI 인스턴스 생성 + 라우터·middleware 등록.

    Args:
        settings: 의존성 주입용 ``Settings``. ``None`` 이면 ``get_settings()``.

    Returns:
        구성 완료된 FastAPI 앱.
    """
    cfg = settings or get_settings()
    app = FastAPI(
        title="Lemon Healthcare API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if cfg.environment != "production" else None,
        redoc_url=None,
    )

    if cfg.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestIdMiddleware)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """헬스 체크 엔드포인트."""
        return {"status": "ok", "environment": cfg.environment}

    app.include_router(auth_router.router, prefix="/api/v1/auth")
    app.include_router(consents_router.router, prefix="/api/v1/consents")
    app.include_router(supplements_router.router, prefix="/api/v1/supplements")

    return app


app = create_app()
