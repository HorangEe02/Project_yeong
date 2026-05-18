"""HTTP middleware — RequestId 자동 생성·전파.

Rate limit / Audit trail 은 FastAPI dependency / service 레이어가 직접 처리하므로
별도 middleware 로 구현하지 않는다 (단순성).

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 9
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """``X-Request-Id`` 헤더 자동 생성·전파.

    클라이언트가 헤더를 제공하면 그대로 사용, 없으면 UUIDv4 발급. 응답 헤더에 동일
    값을 셋하여 로그 추적이 가능하다. ``request.state.request_id`` 로 라우터에서
    접근 가능.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
