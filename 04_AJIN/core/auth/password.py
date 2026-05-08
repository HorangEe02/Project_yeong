"""비밀번호 해싱 유틸리티 — bcrypt 기반"""

import hashlib
import secrets


def hash_password(password: str) -> str:
    """비밀번호를 안전하게 해싱한다 (bcrypt 우선, 폴백: SHA-256+salt)."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    except ImportError:
        # bcrypt 미설치 시 SHA-256 + salt 폴백
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return f"sha256:{salt}:{hashed}"


def verify_password(password: str, password_hash: str) -> bool:
    """비밀번호가 해시와 일치하는지 검증한다."""
    try:
        import bcrypt
        if password_hash.startswith("sha256:"):
            # SHA-256 폴백 형식
            _, salt, hashed = password_hash.split(":")
            return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == hashed
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ImportError:
        if password_hash.startswith("sha256:"):
            _, salt, hashed = password_hash.split(":")
            return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == hashed
        return False


def generate_initial_password(employee_id: str) -> str:
    """초기 비밀번호 생성: ajin + 사원번호 끝 4자리"""
    return f"ajin{employee_id[-4:]}"


# ── SEC-P1: 비밀번호 복잡도 검증 ──

def validate_password_strength(password: str) -> tuple[bool, str]:
    """비밀번호 복잡도를 검증한다.

    Returns:
        (통과 여부, 오류 메시지)
    """
    import re

    if len(password) < 8:
        return False, "비밀번호는 최소 8자 이상이어야 합니다."
    if len(password) > 128:
        return False, "비밀번호는 128자 이하여야 합니다."
    if not re.search(r"[A-Z]", password):
        return False, "영문 대문자를 1개 이상 포함해야 합니다."
    if not re.search(r"[a-z]", password):
        return False, "영문 소문자를 1개 이상 포함해야 합니다."
    if not re.search(r"\d", password):
        return False, "숫자를 1개 이상 포함해야 합니다."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        return False, "특수문자를 1개 이상 포함해야 합니다. (!@#$%^&* 등)"

    # 연속 동일 문자 3회 금지
    for i in range(len(password) - 2):
        if password[i] == password[i + 1] == password[i + 2]:
            return False, "같은 문자를 3번 연속 사용할 수 없습니다."

    return True, ""
