"""Signed httpOnly cookie sessions for ops operators.

Approach
--------
There is **no** `ops_sessions` table. After login the API sets a signed
cookie whose payload is the `ops_users.id` UUID. `itsdangerous`
`URLSafeTimedSerializer` signs and timestamps the value with
`SESSION_SECRET`. Logout clears the cookie. Expiry is `SESSION_TTL_SECONDS`.

This is enough for a single-operator console: revoke means rotating
`SESSION_SECRET` (invalidates every cookie) or waiting for TTL.
"""

import uuid

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.settings import Settings


SESSION_TOKEN_SALT: str = "twerva-ops-session-v1"


class InvalidOpsSessionError(ValueError):
    """Raised when a session cookie is missing, expired, or forged."""


def build_session_token_serializer(session_secret: str) -> URLSafeTimedSerializer:
    """Return the timed signer used for ops session cookies.

    Args:
        session_secret: HMAC secret from `SESSION_SECRET`.

    Returns:
        A serializer bound to the Twerva ops salt.
    """

    session_token_serializer: URLSafeTimedSerializer = URLSafeTimedSerializer(
        session_secret,
        salt=SESSION_TOKEN_SALT,
    )

    return session_token_serializer


def issue_ops_session_token(ops_user_id: uuid.UUID, settings: Settings) -> str:
    """Sign an ops operator id into a cookie value.

    Args:
        ops_user_id: Primary key of the authenticated `ops_users` row.
        settings: Process settings (secret + cookie name are not embedded).

    Returns:
        Signed token to store in the session cookie.
    """

    session_token_serializer: URLSafeTimedSerializer = build_session_token_serializer(
        settings.session_secret,
    )
    signed_session_token: str = session_token_serializer.dumps(str(ops_user_id))

    return signed_session_token


def read_ops_user_id_from_session_token(session_token: str, settings: Settings,
) -> uuid.UUID:
    """Verify a session cookie and return the operator id.

    Args:
        session_token: Raw cookie value.
        settings: Process settings including secret and TTL.

    Returns:
        The `ops_users.id` embedded in the token.

    Raises:
        InvalidOpsSessionError: If the token is blank, expired, or invalid.
    """

    stripped_session_token: str = session_token.strip()

    if stripped_session_token == "":
        raise InvalidOpsSessionError("Session cookie is empty.")

    session_token_serializer: URLSafeTimedSerializer = build_session_token_serializer(
        settings.session_secret,
    )

    try:
        unsigned_payload: object = session_token_serializer.loads(
            stripped_session_token,
            max_age=settings.session_ttl_seconds,
        )
    except SignatureExpired as expired_signature_error:
        raise InvalidOpsSessionError("Session cookie has expired.") from expired_signature_error
    except BadSignature as bad_signature_error:
        raise InvalidOpsSessionError("Session cookie is invalid.") from bad_signature_error

    if not isinstance(unsigned_payload, str):
        raise InvalidOpsSessionError("Session cookie payload is not a user id.")

    try:
        ops_user_id: uuid.UUID = uuid.UUID(unsigned_payload)
    except ValueError as invalid_uuid_error:
        raise InvalidOpsSessionError("Session cookie payload is not a UUID.") from invalid_uuid_error

    return ops_user_id
