"""FastAPI 앱 팩토리.

Phase 00에서 후속 페이즈가 동일한 진입점을 통해 앱을 띄울 수 있도록 미리 구축한다.
Phase 01에서 Redis 풀, Phase 04에서 DB 풀, Phase 05에서 라우터(`auth`, `consents`,
`supplements`)를 추가한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 5
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 10
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import Settings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 시작/종료 시 리소스 초기화·정리 훅.

    Phase 01에서 Redis pool, Phase 04에서 SQLAlchemy AsyncEngine을 본 함수에
    체결한다. Phase 00 시점에는 hook 자리만 둔다.

    Args:
        app: FastAPI 인스턴스.

    Yields:
        None.
    """
    del app  # 후속 페이즈 진입 전까지 사용처 없음
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI 인스턴스를 생성한다.

    Args:
        settings: 의존성 주입용 Settings. ``None`` 이면 ``get_settings()`` 호출.

    Returns:
        구성 완료된 FastAPI 앱.

    Examples:
        >>> app = create_app()
        >>> app.title
        'Lemon Healthcare API'
    """
    cfg = settings or get_settings()
    app = FastAPI(
        title="Lemon Healthcare API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if cfg.environment != "production" else None,
        redoc_url=None,
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """헬스 체크 엔드포인트.

        Returns:
            ``{"status": "ok", "environment": <env>}``.
        """
        return {"status": "ok", "environment": cfg.environment}

    # Phase 05에서 auth, consents, supplements 라우터를 본 함수에 추가한다.
    return app


app = create_app()
