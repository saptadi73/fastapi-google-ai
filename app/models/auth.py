from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Entity, TenantEntity


class Tenant(Entity, Base):
    __tablename__ = "tenant"
    __table_args__ = {"schema": "platform"}
    code: Mapped[str] = mapped_column(String(80), unique=True)


class User(TenantEntity, Base):
    __tablename__ = "app_user"
    __table_args__ = (UniqueConstraint("tenant_id", "username"), {"schema": "platform"})
    username: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(40), default="VIEWER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    row_scope: Mapped[dict] = mapped_column(JSONB, default=dict)


class RefreshToken(TenantEntity, Base):
    __tablename__ = "refresh_token"
    __table_args__ = {"schema": "platform"}
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    jti_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
