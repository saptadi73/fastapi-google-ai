from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.base import now
from app.schemas.common import StrictModel

AccessKind = Literal["DEPARTMENT", "BUSINESS_DOMAIN", "JURISDICTION", "CLEARANCE", "PURPOSE"]
AccessAction = Literal["DISCOVER", "READ", "QUERY", "EXPORT", "EDIT", "APPROVE", "OPERATE", "ADMIN"]


class AccessAttributeCreate(StrictModel):
    kind: AccessKind
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    label: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None
    attribute_data: dict = Field(default_factory=dict)


class AccessAttributeUpdate(StrictModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    is_active: bool | None = None
    attribute_data: dict | None = None
    revision: int = Field(ge=1)


class UserAssignmentCreate(StrictModel):
    attribute_id: UUID
    valid_from: datetime = Field(default_factory=now)
    valid_to: datetime | None = None
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def period_is_valid(self):
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to harus setelah valid_from")
        return self


class AssignmentRevoke(StrictModel):
    revision: int = Field(ge=1)
    note: str = Field(default="", max_length=500)


class PermissionBundleCreate(StrictModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    label: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    actions: list[AccessAction] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def actions_are_unique(self):
        if len(self.actions) != len(set(self.actions)):
            raise ValueError("actions tidak boleh duplikat")
        return self


class PermissionBundleUpdate(StrictModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    actions: list[AccessAction] | None = Field(default=None, min_length=1, max_length=8)
    is_active: bool | None = None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def actions_are_unique(self):
        if self.actions is not None and len(self.actions) != len(set(self.actions)):
            raise ValueError("actions tidak boleh duplikat")
        return self


class PermissionGrantCreate(StrictModel):
    bundle_id: UUID
    valid_from: datetime = Field(default_factory=now)
    valid_to: datetime | None = None
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def period_is_valid(self):
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to harus setelah valid_from")
        return self


class AccessPolicyCreate(StrictModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    label: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    effect: Literal["ALLOW", "DENY"]
    actions: list[AccessAction] = Field(min_length=1, max_length=8)
    required_attribute_ids: list[UUID] = Field(default_factory=list, max_length=100)
    row_scope: dict[str, list[str]] = Field(default_factory=dict)
    column_rules: dict[str, Literal["VISIBLE", "MASKED", "HIDDEN"]] = Field(default_factory=dict)
    export_allowed: bool = False
    valid_from: datetime = Field(default_factory=now)
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_policy(self):
        if len(self.actions) != len(set(self.actions)):
            raise ValueError("actions tidak boleh duplikat")
        if len(self.required_attribute_ids) != len(set(self.required_attribute_ids)):
            raise ValueError("required_attribute_ids tidak boleh duplikat")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to harus setelah valid_from")
        if self.effect == "DENY" and (self.row_scope or self.column_rules or self.export_allowed):
            raise ValueError("DENY tidak menerima row_scope, column_rules, atau export_allowed")
        return self


class AccessPolicyUpdate(StrictModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    effect: Literal["ALLOW", "DENY"] | None = None
    actions: list[AccessAction] | None = Field(default=None, min_length=1, max_length=8)
    required_attribute_ids: list[UUID] | None = Field(default=None, max_length=100)
    row_scope: dict[str, list[str]] | None = None
    column_rules: dict[str, Literal["VISIBLE", "MASKED", "HIDDEN"]] | None = None
    export_allowed: bool | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    revision: int = Field(ge=1)


class AccessPolicyBindingCreate(StrictModel):
    resource_type: Literal["DATA_PRODUCT", "SOURCE", "MASTER", "TAXONOMY"]
    resource_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")


class AccessPolicyTransition(StrictModel):
    revision: int = Field(ge=1)
    note: str = Field(default="", max_length=500)


class AccessEvaluationRequest(StrictModel):
    user_id: UUID | None = None
    action: AccessAction
    resource_type: Literal["DATA_PRODUCT", "SOURCE", "MASTER", "TAXONOMY"]
    resource_id: str = Field(min_length=1, max_length=100)
    at: datetime = Field(default_factory=now)
