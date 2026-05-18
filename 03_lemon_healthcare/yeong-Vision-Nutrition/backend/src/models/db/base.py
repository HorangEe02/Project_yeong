"""SQLAlchemy 2.0 typed declarative base.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 2
    backend/CLAUDE.md Pattern 2
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """모든 ORM 모델의 공통 베이스.

    Alembic ``env.py`` 가 ``Base.metadata`` 를 ``target_metadata`` 로 참조한다.
    플랜에서는 ``MappedAsDataclass`` 도 명시했으나 트랙 B 골격에서는 일반
    ``DeclarativeBase`` 가 더 단순하고 default-value 처리 부담이 적어 선택했다.
    """
