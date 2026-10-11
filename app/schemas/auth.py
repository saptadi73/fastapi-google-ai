from uuid import UUID

from pydantic import Field, SecretStr, model_validator

from app.domain.enums import Role
from app.schemas.common import StrictModel


class LoginRequest(StrictModel):
    tenant_code: str = Field(min_length=1, max_length=80)
    username: str = Field(min_length=1, max_length=100)
    password: SecretStr


class RefreshRequest(StrictModel):
    refresh_token: str = Field(max_length=4096)


class UserCreate(StrictModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: SecretStr = Field(min_length=12, max_length=256)
    full_name: str = Field(default="", max_length=200)
    role: Role = Role.VIEWER
    # product_code -> column_name -> permitted values. Unset means no additional row restriction.
    row_scope: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    initial_access: "InitialAccessRequest | None" = None


class InitialAccessRequest(StrictModel):
    attribute_ids: list[UUID] = Field(default_factory=list, max_length=20)
    bundle_ids: list[UUID] = Field(default_factory=list, max_length=20)
    business_reason: str = Field(min_length=10, max_length=1000)

    @model_validator(mode="after")
    def validate_targets(self):
        if not self.attribute_ids and not self.bundle_ids:
            raise ValueError("Pilih setidaknya satu atribut atau paket izin")
        if len(self.attribute_ids) != len(set(self.attribute_ids)) or len(self.bundle_ids) != len(set(self.bundle_ids)):
            raise ValueError("Target akses tidak boleh berulang")
        return self


class UserUpdate(StrictModel):
    role: Role | None = None
    is_active: bool | None = None
    row_scope: dict[str, dict[str, list[str]]] | None = None


class PasswordChange(StrictModel):
    current_password: SecretStr
    new_password: SecretStr = Field(min_length=12, max_length=256)
