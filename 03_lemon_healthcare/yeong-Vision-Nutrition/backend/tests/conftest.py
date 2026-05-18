"""공통 pytest 픽스처.

unit / integration / e2e 모두에서 공유할 수 있는 픽스처. Phase 00 시점에는 개발자
셸 환경(.env, 셸 export)의 노이즈가 테스트로 새지 않도록 환경 변수를 격리하는
자동 픽스처만 둔다.

후속 페이즈에서 다음을 추가한다:
    - Phase 03: KDRIs CSV / MFDS CSV 픽스처
    - Phase 04: testcontainers Postgres 픽스처
    - Phase 05: TestClient + dependency_overrides

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 6
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from src.config import get_settings

_SAFE_TEST_ENV: dict[str, str] = {
    "ENVIRONMENT": "development",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_PROVIDER": "ollama",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "OLLAMA_MODEL": "qwen3.5:9b",
    "OLLAMA_MULTIMODAL_MODEL": "gemma4:e4b",
    "ENABLE_MULTIMODAL_LLM": "false",
    "ENABLE_VISION_CLASSIFIER": "false",
    "ENABLE_IMAGE_LEARNING_PIPELINE": "false",
    "ENABLE_PGVECTOR_STORAGE": "false",
    "IMAGE_RETENTION_TEMPORARY_HOURS": "0",
    "IMAGE_RETENTION_HISTORY_DAYS": "90",
    "IMAGE_RETENTION_TRAINING_DAYS": "0",
    "LOG_LEVEL": "INFO",
    "JWT_SECRET_KEY": "test-secret-key-do-not-use-in-production",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_TTL_MINUTES": "15",
    "REFRESH_TOKEN_TTL_DAYS": "14",
    "CORS_ALLOWED_ORIGINS": "[]",
    "RATE_LIMIT_REGISTER_PER_MINUTE": "10",
    "IP_HASH_SALT": "test-salt",
}


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """모든 테스트의 환경 변수를 격리한다.

    개발자 셸의 환경 변수나 작업 디렉터리의 ``.env`` 가 테스트로 새지 않도록
    명시된 안전 기본값만 주입한다. ``get_settings`` 의 ``lru_cache`` 도 함께
    리셋해 테스트 간 격리를 보장한다.
    """
    for key, value in _SAFE_TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
