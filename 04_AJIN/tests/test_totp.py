"""v4.7 Feature E Phase 2 — TOTP 2FA 단위 테스트.

검증:
  1. enroll → secret 생성 + Fernet 암호화 + otpauth URL
  2. confirm → 올바른 코드로 totp_enabled=1
  3. verify TOTP code (window 1 — drift 30초 허용)
  4. backup code 1회 소비
  5. 5회 실패 → 30분 잠금
  6. regenerate_backup_codes
"""

from __future__ import annotations

import pytest


@pytest.fixture
def fernet_key(monkeypatch):
    from cryptography.fernet import Fernet  # type: ignore

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("TOTP_SECRET_FERNET_KEY", key)
    return key


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr("core.auth.database.AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    from core.auth import database as _db

    monkeypatch.setattr(_db, "AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    _db.init_auth_db()

    # 테스트 사용자 — EMPLOYEE 권한
    from core.auth.password import hash_password

    conn = _db.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name='EMPLOYEE'").fetchone()
    conn.execute(
        """INSERT INTO users (employee_id, username, password_hash, role_id, is_active, must_change_pw)
           VALUES ('TEST-0001', 'TestUser', ?, ?, 1, 0)""",
        (hash_password("pw123456"), role["role_id"]),
    )
    conn.commit()
    conn.close()
    return tmp_path / "auth.db"


def test_fernet_key_missing_raises(monkeypatch):
    monkeypatch.delenv("TOTP_SECRET_FERNET_KEY", raising=False)
    from features.admin import totp

    with pytest.raises(ValueError, match="TOTP_SECRET_FERNET_KEY"):
        totp._get_fernet()


def test_enroll_generates_secret_and_codes(fernet_key, isolated_db):
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    assert isinstance(result["secret_b32"], str)
    assert len(result["secret_b32"]) >= 16
    assert result["otpauth_url"].startswith("otpauth://totp/")
    assert "AJIN-AI-Assistant" in result["otpauth_url"]
    assert len(result["backup_codes"]) == 8
    # 코드 형식: 5+5 헥사
    for code in result["backup_codes"]:
        assert len(code) == 11
        assert code[5] == "-"
    # enabled 는 아직 false (confirm 전)
    assert not totp.is_enabled("TEST-0001")


def test_confirm_with_correct_code_enables(fernet_key, isolated_db):
    import pyotp  # type: ignore
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    code = pyotp.TOTP(result["secret_b32"]).now()
    assert totp.confirm_enrollment("TEST-0001", code) is True
    assert totp.is_enabled("TEST-0001")


def test_confirm_with_wrong_code_fails(fernet_key, isolated_db):
    from features.admin import totp

    totp.enroll_user("TEST-0001")
    assert totp.confirm_enrollment("TEST-0001", "000000") is False
    assert not totp.is_enabled("TEST-0001")


def test_verify_totp_code_after_enable(fernet_key, isolated_db):
    import pyotp  # type: ignore
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    secret = result["secret_b32"]
    totp.confirm_enrollment("TEST-0001", pyotp.TOTP(secret).now())

    # 정상 코드
    assert totp.verify_code("TEST-0001", pyotp.TOTP(secret).now()) is True


def test_verify_window_drift(fernet_key, isolated_db):
    """window=1 — 30초 전후 코드도 허용."""
    import pyotp  # type: ignore
    import time
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    secret = result["secret_b32"]
    totp.confirm_enrollment("TEST-0001", pyotp.TOTP(secret).now())

    # 30초 이전 코드 (counter-1) → 유효해야 함
    t = int(time.time())
    prev_code = pyotp.TOTP(secret).at(t - 30)
    assert totp.verify_code("TEST-0001", prev_code) is True


def test_backup_code_consumed_once(fernet_key, isolated_db):
    import pyotp  # type: ignore
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    secret = result["secret_b32"]
    totp.confirm_enrollment("TEST-0001", pyotp.TOTP(secret).now())
    backup = result["backup_codes"][0]

    # 1회차: 성공
    assert totp.verify_code("TEST-0001", backup) is True
    # 2회차: 같은 코드 거부 (1회 소비)
    assert totp.verify_code("TEST-0001", backup) is False


def test_five_failed_codes_lock_account(fernet_key, isolated_db):
    import pyotp  # type: ignore
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    secret = result["secret_b32"]
    totp.confirm_enrollment("TEST-0001", pyotp.TOTP(secret).now())

    for _ in range(5):
        assert totp.verify_code("TEST-0001", "000000") is False

    # 잠금 상태 — 올바른 코드도 거부 (locked_until 미래)
    correct = pyotp.TOTP(secret).now()
    assert totp.verify_code("TEST-0001", correct) is False


def test_regenerate_backup_codes_invalidates_old(fernet_key, isolated_db):
    import pyotp  # type: ignore
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    totp.confirm_enrollment("TEST-0001", pyotp.TOTP(result["secret_b32"]).now())
    old_codes = result["backup_codes"]

    new_codes = totp.regenerate_backup_codes("TEST-0001")
    assert len(new_codes) == 8
    assert set(new_codes).isdisjoint(set(old_codes))

    # 옛 백업코드 거부
    assert totp.verify_code("TEST-0001", old_codes[0]) is False
    # 새 백업코드 통과
    assert totp.verify_code("TEST-0001", new_codes[0]) is True


def test_disable_2fa_clears_state(fernet_key, isolated_db):
    import pyotp  # type: ignore
    from features.admin import totp

    result = totp.enroll_user("TEST-0001")
    totp.confirm_enrollment("TEST-0001", pyotp.TOTP(result["secret_b32"]).now())
    assert totp.is_enabled("TEST-0001")

    totp.disable_2fa("TEST-0001")
    assert not totp.is_enabled("TEST-0001")
