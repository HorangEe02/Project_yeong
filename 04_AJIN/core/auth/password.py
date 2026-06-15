"""Password hashing and policy utilities for AJIN auth.

The backend owns password policy enforcement. Frontend checks are only a UX
preview and must not be treated as authorization logic.
"""

import hashlib
import os
import re
import secrets
import string
import unicodedata

BCRYPT_MAX_BYTES = 72
MIN_PASSWORD_LENGTH = 12
TEMP_PASSWORD_LENGTH = 20

_TRUTHY = {"1", "true", "yes", "on"}
_PRODUCTION_VALUES = {"prod", "production", "real", "real_only"}
_TEMP_SYMBOLS = "!@#$%^&*()-_=+[]{}?"
_COMMON_PASSWORDS = {
    "admin",
    "admin1234",
    "ajin1234",
    "ajinadmin",
    "password",
    "password1",
    "password123",
    "qwerty",
    "qwerty123",
    "12345678",
    "123456789",
    "11111111",
    "letmein",
    "welcome",
}
_CONTEXT_WORDS = {
    "ajin",
    "ajinindustry",
    "assistant",
    "administrator",
    "system",
    "sysadmin",
}


def is_production_runtime() -> bool:
    """Return whether the current process is running in a production posture.

    Returns:
        bool: True for Cloud Run or explicit production/real environment modes.
    """

    if os.getenv("K_SERVICE"):
        return True
    for name in ("AJIN_ENVIRONMENT", "APP_ENV", "ENVIRONMENT", "AJIN_DATA_CLASS_MODE"):
        if os.getenv(name, "").strip().lower() in _PRODUCTION_VALUES:
            return True
    return False


def bcrypt_available() -> bool:
    """Check whether bcrypt can be imported.

    Returns:
        bool: True when the bcrypt package is installed.
    """

    try:
        import bcrypt  # noqa: F401
    except ImportError:
        return False
    return True


def require_bcrypt_for_passwords() -> None:
    """Fail closed in production if bcrypt is unavailable.

    Raises:
        RuntimeError: If production runtime would fall back to SHA-256.
    """

    if is_production_runtime() and not bcrypt_available():
        raise RuntimeError("bcrypt is required for production password hashing")


def hash_password(password: str) -> str:
    """Hash a password.

    Args:
        password: Plain text password.

    Returns:
        str: Stored password hash.

    Raises:
        ValueError: If the password exceeds bcrypt's safe input length.
        RuntimeError: If bcrypt is unavailable in production.
    """

    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
    try:
        import bcrypt

        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    except ImportError:
        require_bcrypt_for_passwords()
        # Local/dev fallback only. Production fails closed above.
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return f"sha256:{salt}:{hashed}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash.

    Args:
        password: Candidate password.
        password_hash: Stored bcrypt or legacy local SHA-256 hash.

    Returns:
        bool: True if the candidate matches.
    """

    try:
        import bcrypt
        if password_hash.startswith("sha256:"):
            # SHA-256 폴백 형식
            _, salt, hashed = password_hash.split(":")
            return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == hashed
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ImportError:
        require_bcrypt_for_passwords()
        if password_hash.startswith("sha256:"):
            _, salt, hashed = password_hash.split(":")
            return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == hashed
        return False
    except (TypeError, ValueError):
        return False


def generate_initial_password(employee_id: str | None = None) -> str:
    """Generate a one-time temporary password.

    Args:
        employee_id: Ignored legacy parameter kept for caller compatibility.

    Returns:
        str: Random temporary password suitable for one-time issuance.
    """

    del employee_id
    rng = secrets.SystemRandom()
    required = [
        rng.choice(string.ascii_lowercase),
        rng.choice(string.ascii_uppercase),
        rng.choice(string.digits),
        rng.choice(_TEMP_SYMBOLS),
    ]
    alphabet = string.ascii_letters + string.digits + _TEMP_SYMBOLS
    required.extend(rng.choice(alphabet) for _ in range(TEMP_PASSWORD_LENGTH - len(required)))
    rng.shuffle(required)
    return "".join(required)


# ── SEC-P1: 비밀번호 복잡도 검증 ──

def _normalized_password(password: str) -> str:
    """Normalize a password before policy checks.

    Args:
        password: Candidate password.

    Returns:
        str: NFC-normalized password.
    """

    return unicodedata.normalize("NFC", password or "")


def _context_candidates(*values: str) -> set[str]:
    """Build context-specific blocklist candidates.

    Args:
        *values: Employee id, username, service names, or related identifiers.

    Returns:
        set[str]: Lowercase candidate words and simple derivatives.
    """

    words = set(_CONTEXT_WORDS)
    for value in values:
        lowered = re.sub(r"\s+", "", (value or "").strip().lower())
        if not lowered:
            continue
        words.add(lowered)
        words.add(re.sub(r"[^a-z0-9가-힣]", "", lowered))
    words.discard("")
    candidates: set[str] = set()
    for word in words:
        candidates.add(word)
        candidates.add(f"{word}1")
        candidates.add(f"{word}12")
        candidates.add(f"{word}123")
        candidates.add(f"{word}1234")
        candidates.add(f"{word}!")
        candidates.add(f"{word}!!")
        candidates.add(f"{word}@123")
    return candidates


def validate_password_strength(
    password: str,
    *,
    employee_id: str = "",
    username: str = "",
    extra_context: tuple[str, ...] = (),
) -> tuple[bool, str]:
    """Validate the backend password policy.

    Args:
        password: Candidate password.
        employee_id: User employee id for context-specific blocklist checks.
        username: User display name for context-specific blocklist checks.
        extra_context: Additional words that should not be used as passwords.

    Returns:
        tuple[bool, str]: Pass status and user-facing rejection reason.
    """

    normalized = _normalized_password(password)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        return False, f"비밀번호는 최소 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
    if len(normalized.encode("utf-8")) > BCRYPT_MAX_BYTES:
        return False, "비밀번호는 UTF-8 기준 72바이트 이하여야 합니다."

    lowered = normalized.strip().lower()
    simplified = re.sub(r"[^a-z0-9가-힣]", "", lowered)
    if (
        lowered in _COMMON_PASSWORDS
        or simplified in _COMMON_PASSWORDS
        or any(len(word) >= 8 and word in simplified for word in _COMMON_PASSWORDS)
    ):
        return False, "너무 흔한 비밀번호는 사용할 수 없습니다."
    context_candidates = _context_candidates(employee_id, username, *extra_context)
    if (
        lowered in context_candidates
        or simplified in context_candidates
        or any(len(word) >= 4 and word in simplified for word in context_candidates)
    ):
        return False, "사번, 이름, 서비스명과 유사한 비밀번호는 사용할 수 없습니다."

    return True, ""


def validate_password_change(
    new_password: str,
    *,
    current_password_hash: str = "",
    previous_password_hashes: tuple[str, ...] = (),
    employee_id: str = "",
    username: str = "",
) -> tuple[bool, str]:
    """Validate a password change request against policy and history.

    Args:
        new_password: Candidate new password.
        current_password_hash: Current stored password hash.
        previous_password_hashes: Recent password history hashes.
        employee_id: User employee id.
        username: User display name.

    Returns:
        tuple[bool, str]: Pass status and user-facing rejection reason.
    """

    ok, message = validate_password_strength(
        new_password,
        employee_id=employee_id,
        username=username,
    )
    if not ok:
        return ok, message
    if current_password_hash and verify_password(new_password, current_password_hash):
        return False, "현재 비밀번호와 같은 비밀번호는 사용할 수 없습니다."
    for password_hash in previous_password_hashes:
        if password_hash and verify_password(new_password, password_hash):
            return False, "최근 사용한 비밀번호는 다시 사용할 수 없습니다."
    return True, ""
