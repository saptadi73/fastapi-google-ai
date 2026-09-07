from pydantic import Field, SecretStr

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


class UserUpdate(StrictModel):
    role: Role | None = None
    is_active: bool | None = None
    row_scope: dict[str, dict[str, list[str]]] | None = None


class PasswordChange(StrictModel):
    current_password: SecretStr
    new_password: SecretStr = Field(min_length=12, max_length=256)
