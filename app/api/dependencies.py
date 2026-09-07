from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.models.auth import User

Session = Annotated[AsyncSession, Depends(get_session)]
bearer = HTTPBearer(auto_error=False)


async def current_user(
    session: Session, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
):
    if not credentials:
        raise AppError("AUTHENTICATION_REQUIRED", "Bearer token diperlukan.", 401)
    claims = decode_token(credentials.credentials)
    try:
        user_id = str(UUID(claims["sub"]))
        tenant_id = str(UUID(claims["tenant_id"]))
    except (ValueError, TypeError):
        raise AppError("INVALID_TOKEN", "Token tidak valid.", 401) from None
    user = await session.get(User, user_id)
    if not user or not user.is_active or user.tenant_id != tenant_id or user.token_version != claims["ver"]:
        raise AppError("INVALID_TOKEN", "Token tidak valid.", 401)
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles):
    async def allowed(user: CurrentUser):
        if user.role not in roles:
            raise AppError("FORBIDDEN", "Role tidak memiliki izin untuk tindakan ini.", 403)
        return user

    return allowed
