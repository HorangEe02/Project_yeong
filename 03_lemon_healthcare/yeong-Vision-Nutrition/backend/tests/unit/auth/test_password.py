"""``src.auth.password`` 단위 테스트."""

from __future__ import annotations

from src.auth.password import hash_password, verify_password


def test_hash_then_verify_correct_returns_true() -> None:
    plain = "s3cret-passw0rd"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_wrong_password_returns_false() -> None:
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_hash_is_not_plain_text() -> None:
    plain = "abcd1234"
    hashed = hash_password(plain)
    assert plain not in hashed


def test_hash_uses_bcrypt_prefix() -> None:
    """bcrypt 해시는 ``$2b$`` 또는 ``$2a$`` 로 시작한다."""
    hashed = hash_password("any")
    assert hashed.startswith(("$2b$", "$2a$", "$2y$"))


def test_hashes_differ_for_same_plain_text() -> None:
    """같은 평문도 매번 다른 salt 로 해시되어야 한다."""
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)
