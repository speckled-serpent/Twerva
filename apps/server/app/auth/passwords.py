"""bcrypt helpers for ops operator passwords.

Never log the plaintext password. Hashes are stored on `ops_users.password_hash`.
"""

import bcrypt


BCRYPT_ROUNDS: int = 12


def hash_plain_password(plain_password: str) -> str:
    """Return a bcrypt hash for a plaintext password.

    Args:
        plain_password: Operator password from login or bootstrap env.

    Returns:
        UTF-8 bcrypt hash string suitable for `ops_users.password_hash`.
    """

    password_bytes: bytes = plain_password.encode("utf-8")
    salt_bytes: bytes = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed_bytes: bytes = bcrypt.hashpw(password_bytes, salt_bytes)
    password_hash: str = hashed_bytes.decode("utf-8")

    return password_hash


def plain_password_matches_hash(plain_password: str, password_hash: str) -> bool:
    """Return True when `plain_password` verifies against `password_hash`.

    Args:
        plain_password: Password submitted on login.
        password_hash: Stored bcrypt hash.

    Returns:
        True when the password matches; False on mismatch or invalid hash.
    """

    password_bytes: bytes = plain_password.encode("utf-8")
    hash_bytes: bytes = password_hash.encode("utf-8")

    try:
        passwords_match: bool = bcrypt.checkpw(password_bytes, hash_bytes)
    except ValueError:
        passwords_match = False

    return passwords_match
