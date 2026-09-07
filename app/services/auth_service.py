import hashlib

from sqlalchemy import select

from app.core.exceptions import AppError
from app.core.security import DUMMY_HASH, decode_token, issue_token, password_hasher
from app.models.auth import RefreshToken, Tenant, User
from app.models.base import now
from app.repositories.base import TenantRepository, record
from app.services.audit_service import audit


def public_user(user):
    return record(user, exclude=("password_hash", "token_version"))


async def token_pair(session, user):
    access, _ = issue_token(user, "access")
    refresh, claims = issue_token(user, "refresh")
    session.add(
        RefreshToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            jti_hash=hashlib.sha256(claims["jti"].encode()).hexdigest(),
            expires_at=claims["exp"],
        )
    )
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


class AuthService:
    def __init__(self, session):
        self.session = session

    async def login(self, data):
        user = await self.session.scalar(
            select(User).join(Tenant).where(Tenant.code == data.tenant_code, User.username == data.username)
        )
        valid = password_hasher.verify(
            data.password.get_secret_value(), user.password_hash if user else DUMMY_HASH
        )
        if not user or not valid or not user.is_active:
            raise AppError("INVALID_CREDENTIALS", "Tenant, username, atau password salah.", 401)
        audit(self.session, user, "auth.login")
        return await token_pair(self.session, user)

    async def refresh(self, token):
        claims = decode_token(token, "refresh")
        token_row = await self.session.scalar(
            select(RefreshToken)
            .where(
                RefreshToken.jti_hash == hashlib.sha256(claims["jti"].encode()).hexdigest(),
                RefreshToken.tenant_id == claims["tenant_id"],
            )
            .with_for_update()
        )
        user = await self.session.get(User, claims["sub"])
        if (
            not token_row
            or token_row.revoked
            or token_row.expires_at <= now()
            or not user
            or not user.is_active
            or user.tenant_id != claims["tenant_id"]
            or user.token_version != claims["ver"]
        ):
            raise AppError("INVALID_TOKEN", "Refresh token tidak valid.", 401)
        token_row.revoked = True
        return await token_pair(self.session, user)

    async def create_user(self, actor, data):
        repo = TenantRepository(self.session, actor.tenant_id)
        user = await repo.add(
            User,
            username=data.username,
            full_name=data.full_name,
            password_hash=password_hasher.hash(data.password.get_secret_value()),
            role=data.role.value,
            row_scope=data.row_scope,
        )
        audit(self.session, actor, "user.created", user.id)
        return public_user(user)

    async def update_user(self, actor, user_id, data):
        user = await TenantRepository(self.session, actor.tenant_id).get(User, user_id, lock=True)
        if user.id == actor.id and (data.is_active is False or (data.role and data.role != actor.role)):
            raise AppError("SELF_LOCKOUT", "Gunakan admin lain untuk mengubah akses akun sendiri.")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(user, field, value.value if hasattr(value, "value") else value)
        user.token_version += 1
        audit(self.session, actor, "user.updated", user.id)
        return public_user(user)

    async def change_password(self, user, data):
        if not password_hasher.verify(data.current_password.get_secret_value(), user.password_hash):
            raise AppError("INVALID_CREDENTIALS", "Password saat ini salah.", 401)
        user.password_hash = password_hasher.hash(data.new_password.get_secret_value())
        user.token_version += 1
        audit(self.session, user, "auth.password_changed")
