"""pytest 공용 conftest — 프로젝트 루트 sys.path 등록 + asyncio 모드 설정.

- `from __future__ import annotations` 로 type hint 평가 지연
- 프로젝트 루트를 sys.path[0] 로 보장 (테스트가 어느 디렉토리에서 실행되든 `from core.*` import 가능)
- pytest-asyncio 의 asyncio_mode 는 pyproject 가 없으므로 ini-options 형태로 conftest 에서 동적 설정
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 프로젝트 루트를 sys.path 에 등록
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_collection_modifyitems(config, items):
    """asyncio 마커 자동 부착 — async def 테스트는 자동으로 @pytest.mark.asyncio 로 마킹."""
    for item in items:
        if isinstance(item, pytest.Function) and item.get_closest_marker("asyncio") is None:
            # async 함수면 마커 자동 추가
            import inspect
            if inspect.iscoroutinefunction(item.function):
                item.add_marker(pytest.mark.asyncio)
