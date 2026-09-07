from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import AppError

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("invalid-account-timing-placeholder")


def issue_token(user, kind: str) -> tuple[str, dict]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    lifetime = (
        timedelta(minutes=s.jwt_access_minutes) if kind == "access" else timedelta(days=s.jwt_refresh_days)
    )
    claims = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "roles": [user.role],
        "type": kind,
        "jti": str(uuid4()),
        "ver": user.token_version,
        "iat": now,
        "nbf": now,
        "exp": now + lifetime,
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
    }
    return jwt.encode(claims, s.jwt_secret.get_secret_value(), algorithm="HS256"), claims


def decode_token(token: str, kind="access"):
    s = get_settings()
    try:
        claims = jwt.decode(
            token,
            s.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer=s.jwt_issuer,
            audience=s.jwt_audience,
            options={"require": ["sub", "tenant_id", "exp", "iat", "nbf", "jti", "type", "ver"]},
        )
        if claims["type"] != kind:
            raise ValueError("wrong token type")
        return claims
    except (jwt.PyJWTError, ValueError):
        raise AppError("INVALID_TOKEN", "Token tidak valid atau kedaluwarsa.", 401) from None
