"""bcrypt 기반 비밀번호 해싱 / 검증.

설계 결정 — passlib 우회 사유:
    ``passlib[bcrypt]>=1.7`` 은 ``bcrypt`` 4.x 와 호환되지 않는다 (passlib 가
    bcrypt 4.x의 ``__about__`` 모듈을 더 이상 export 하지 않는 변경을 따라가지
    못함). ``bcrypt`` 라이브러리 자체가 안정적이고 API 가 작으므로 ``passlib``
    의존성을 빼고 직접 호출한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 1
"""

from __future__ import annotations

from typing import Final

import bcrypt

_BCRYPT_ROUNDS: Final[int] = 12


def hash_password(plain: str) -> str:
    """평문 비밀번호를 bcrypt 해시로 변환한다.

    Args:
        plain: 평문 비밀번호.

    Returns:
        bcrypt 해시 문자열 (``$2b$`` 로 시작, 60자 내외).
    """
    digest = bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    )
    return digest.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """평문이 저장된 해시와 일치하는지 검증한다.

    Args:
        plain: 평문 비밀번호.
        hashed: ``hash_password`` 가 생성한 해시.

    Returns:
        일치 여부. 해시 형식이 잘못된 경우에도 ``False`` 를 반환한다.
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
