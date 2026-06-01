"""v4.7 Feature E Phase 2 — 관리자/사용자 TOTP 2FA.

흐름:
  1. enroll_user(employee_id) → pyotp.random_base32 시크릿 생성 + Fernet 암호화 저장
     + 8개 backup code (bcrypt hash) 생성 + otpauth URL 반환
  2. confirm_enrollment(employee_id, code) → pyotp.TOTP.verify (window=1) 통과 시 totp_enabled=1
  3. verify_code(employee_id, code) → 1) TOTP 코드 또는 2) backup code (1회 소비)
  4. regenerate_backup_codes(employee_id) → 신규 8 코드 (재발급)

저장 모델 (users 테이블 5컬럼, v4.7 마이그레이션):
  totp_secret        BLOB    Fernet 암호화된 base32 secret
  backup_codes_hash  TEXT    8개 코드의 bcrypt hash, ':' 구분
  totp_enabled       INT(0|1)
  totp_failed_count  INT     5회 실패 시 잠금
  totp_locked_until  TEXT    ISO datetime
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ISSUER = "AJIN-AI-Assistant"
BACKUP_CODES_COUNT = 8
TOTP_MAX_FAILED = 5
TOTP_LOCK_MINUTES = 30


def _get_fernet():
    """env `TOTP_SECRET_FERNET_KEY` 로 Fernet 인스턴스 생성.

    키 누락 시 ValueError raise — 부팅·enroll 시점에 즉시 실패해 운영자가 인지.
    Fernet.generate_key() 로 생성한 32바이트 base64 키 (44자 + '=').
    """
    from cryptography.fernet import Fernet  # type: ignore

    key = os.environ.get("TOTP_SECRET_FERNET_KEY", "").strip().encode()
    if not key:
        raise ValueError(
            "TOTP_SECRET_FERNET_KEY 환경변수 미설정 — 2FA 기능 사용 불가. "
            "`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` 로 생성."
        )
    try:
        return Fernet(key)
    except Exception as e:
        raise ValueError(f"TOTP_SECRET_FERNET_KEY 형식 오류: {e}") from e


def _encrypt_secret(secret: str) -> bytes:
    return _get_fernet().encrypt(secret.encode())


def _decrypt_secret(blob: bytes) -> str:
    return _get_fernet().decrypt(blob).decode()


def _generate_backup_codes() -> tuple[list[str], str]:
    """8개의 6+4 형식 코드 생성. 반환: (raw codes, bcrypt hash joined by ':')."""
    from core.auth.password import hash_password

    codes: list[str] = []
    hashes: list[str] = []
    for _ in range(BACKUP_CODES_COUNT):
        # 10자리 영숫자 (24비트 엔트로피 충분)
        token = secrets.token_hex(5).upper()  # 10자
        code = f"{token[:5]}-{token[5:]}"
        codes.append(code)
        hashes.append(hash_password(code))
    return codes, ":".join(hashes)


def _get_user_row(employee_id: str):
    from core.auth.database import get_auth_db

    conn = get_auth_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE employee_id = ?", (employee_id,)
        ).fetchone()
    finally:
        conn.close()


def enroll_user(employee_id: str) -> dict[str, object]:
    """2FA enroll — 시크릿 생성 + 백업코드 생성. totp_enabled 는 confirm 시 1로.

    Returns:
        {
          "secret_b32": str,     # 사용자에게 표시될 base32 secret (수동 입력용)
          "otpauth_url": str,    # QR 코드 인코딩용 otpauth:// URL
          "backup_codes": list[str],
          "issuer": str,
        }
    """
    import pyotp  # type: ignore

    from core.auth.database import get_auth_db

    row = _get_user_row(employee_id)
    if not row:
        raise ValueError(f"사용자 없음: {employee_id}")

    secret = pyotp.random_base32()
    encrypted = _encrypt_secret(secret)

    codes, codes_hash = _generate_backup_codes()

    conn = get_auth_db()
    try:
        conn.execute(
            """UPDATE users
               SET totp_secret = ?, backup_codes_hash = ?, totp_enabled = 0,
                   totp_failed_count = 0, totp_locked_until = NULL,
                   updated_at = datetime('now')
               WHERE employee_id = ?""",
            (encrypted, codes_hash, employee_id),
        )
        conn.commit()
    finally:
        conn.close()

    username = row["username"] or employee_id
    otpauth = pyotp.TOTP(secret).provisioning_uri(
        name=f"{username} ({employee_id})",
        issuer_name=ISSUER,
    )
    return {
        "secret_b32": secret,
        "otpauth_url": otpauth,
        "backup_codes": codes,
        "issuer": ISSUER,
    }


def confirm_enrollment(employee_id: str, code: str) -> bool:
    """enroll 직후 사용자가 인증앱에서 받은 코드로 enrollment 확정."""
    import pyotp  # type: ignore

    from core.auth.database import get_auth_db

    row = _get_user_row(employee_id)
    if not row or not row["totp_secret"]:
        raise ValueError("enroll 되지 않은 사용자")

    secret = _decrypt_secret(row["totp_secret"])
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False

    conn = get_auth_db()
    try:
        conn.execute(
            """UPDATE users
               SET totp_enabled = 1, totp_failed_count = 0, totp_locked_until = NULL,
                   updated_at = datetime('now')
               WHERE employee_id = ?""",
            (employee_id,),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def verify_code(employee_id: str, code: str) -> bool:
    """TOTP 코드 또는 백업코드 검증. 백업코드 일치 시 해당 코드 1회 소비.

    5회 실패 시 30분 잠금. 잠금 중에는 모든 코드 거부.
    """
    import pyotp  # type: ignore

    from core.auth.database import get_auth_db
    from core.auth.password import verify_password

    row = _get_user_row(employee_id)
    if not row or not row["totp_enabled"] or not row["totp_secret"]:
        return False

    # 잠금 확인
    locked_until = row["totp_locked_until"]
    if locked_until:
        try:
            lu = datetime.fromisoformat(locked_until)
            if lu > datetime.now(timezone.utc):
                return False
        except ValueError:
            pass

    secret = _decrypt_secret(row["totp_secret"])
    ok = False

    # 1) TOTP 검증 (window=1 — 30초 ± 1)
    if pyotp.TOTP(secret).verify(code, valid_window=1):
        ok = True

    # 2) 백업코드 검증 (1회 소비)
    consumed_idx: int | None = None
    if not ok and row["backup_codes_hash"]:
        hashes = row["backup_codes_hash"].split(":")
        for i, h in enumerate(hashes):
            if h and verify_password(code, h):
                consumed_idx = i
                ok = True
                break

    conn = get_auth_db()
    try:
        if ok:
            updates = "totp_failed_count = 0, totp_locked_until = NULL"
            params: list[object] = []
            if consumed_idx is not None:
                hashes = row["backup_codes_hash"].split(":")
                hashes[consumed_idx] = ""  # 1회 소비 — 빈 슬롯
                updates += ", backup_codes_hash = ?"
                params.append(":".join(hashes))
            params.append(employee_id)
            conn.execute(
                f"UPDATE users SET {updates}, updated_at = datetime('now') WHERE employee_id = ?",
                params,
            )
        else:
            new_failed = (row["totp_failed_count"] or 0) + 1
            if new_failed >= TOTP_MAX_FAILED:
                lock = (datetime.now(timezone.utc) + timedelta(minutes=TOTP_LOCK_MINUTES)).isoformat()
                conn.execute(
                    """UPDATE users SET totp_failed_count = ?, totp_locked_until = ?
                       WHERE employee_id = ?""",
                    (new_failed, lock, employee_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET totp_failed_count = ? WHERE employee_id = ?",
                    (new_failed, employee_id),
                )
        conn.commit()
    finally:
        conn.close()
    return ok


def regenerate_backup_codes(employee_id: str) -> list[str]:
    """백업코드 8개 재발급 — 기존 코드 모두 무효."""
    from core.auth.database import get_auth_db

    row = _get_user_row(employee_id)
    if not row:
        raise ValueError(f"사용자 없음: {employee_id}")

    codes, codes_hash = _generate_backup_codes()
    conn = get_auth_db()
    try:
        conn.execute(
            """UPDATE users SET backup_codes_hash = ?, updated_at = datetime('now')
               WHERE employee_id = ?""",
            (codes_hash, employee_id),
        )
        conn.commit()
    finally:
        conn.close()
    return codes


def disable_2fa(employee_id: str) -> None:
    """2FA 비활성 — 시크릿/백업코드/잠금 모두 초기화."""
    from core.auth.database import get_auth_db

    conn = get_auth_db()
    try:
        conn.execute(
            """UPDATE users
               SET totp_enabled = 0, totp_secret = NULL, backup_codes_hash = '',
                   totp_failed_count = 0, totp_locked_until = NULL,
                   updated_at = datetime('now')
               WHERE employee_id = ?""",
            (employee_id,),
        )
        conn.commit()
    finally:
        conn.close()


def is_enabled(employee_id: str) -> bool:
    row = _get_user_row(employee_id)
    return bool(row and row["totp_enabled"])
