from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import StrictModel
from app.schemas.configuration import ColumnMapping, PGType
from app.schemas.data_policy import MasterImportPolicy


class MasterField(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    type: PGType
    nullable: bool = True
    pii_classification: str = Field(default="NONE", pattern=r"^(NONE|LOW|MEDIUM|HIGH)$")


class MasterSchema(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    fields: list[MasterField] = Field(min_length=1, max_length=100)
    business_key: list[str] = Field(min_length=1, max_length=10)
    label_field: str
    policy: MasterImportPolicy

    @field_validator("name")
    @classmethod
    def trimmed_name(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("Nama wajib terisi")
        return value

    @field_validator("aliases")
    @classmethod
    def valid_aliases(cls, values):
        values = [" ".join(v.split()) for v in values]
        if any(not v or len(v) > 200 for v in values) or len({v.casefold() for v in values}) != len(values):
            raise ValueError("Alias wajib terisi, unik, dan maksimal 200 karakter")
        return values

    @model_validator(mode="after")
    def validate_fields(self):
        fields = {f.name: f for f in self.fields}
        if len(fields) != len(self.fields):
            raise ValueError("Nama field harus unik")
        if len(set(self.business_key)) != len(self.business_key) or not set(self.business_key).issubset(
            fields
        ):
            raise ValueError("Business key harus unik dan merujuk field master")
        if any(fields[key].nullable for key in self.business_key):
            raise ValueError("Business key tidak boleh nullable")
        if self.label_field not in fields:
            raise ValueError("Label harus merujuk field master")
        if period := self.policy.effective_dating:
            for name in (period.valid_from_column, period.valid_to_column):
                if name not in fields or fields[name].type not in ("date", "timestamp", "timestamptz"):
                    raise ValueError("Masa berlaku harus merujuk field tanggal/waktu")
            if fields[period.valid_from_column].type != fields[period.valid_to_column].type:
                raise ValueError("Tipe awal dan akhir masa berlaku harus sama")
            if period.valid_from_column not in self.business_key or len(self.business_key) < 2:
                raise ValueError("Effective dating requires entity key plus valid_from in business_key")
            if period.valid_to_column in self.business_key:
                raise ValueError("valid_to cannot be part of the version business_key")
        return self


class MasterDefinitionCreate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    definition: MasterSchema
    reviewed_candidate_ids: list[UUID] = Field(default_factory=list, max_length=100)
    duplicate_review_reason: str = Field(default="", max_length=2000)


class MasterDefinitionPatch(StrictModel):
    revision_no: int = Field(ge=1)
    definition: MasterSchema
    reviewed_candidate_ids: list[UUID] = Field(default_factory=list, max_length=100)
    duplicate_review_reason: str = Field(default="", max_length=2000)


class MasterRevisionRequest(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)


class MasterBindingUpdate(StrictModel):
    revision_no: int = Field(ge=0)  # 0 creates the first binding; subsequent updates use its revision.
    master_definition_id: UUID
    master_version: int = Field(ge=1)
    classification_revision: int = Field(ge=1)
    columns: list[ColumnMapping] = Field(min_length=1, max_length=100)


class MasterColumnBindingCreate(StrictModel):
    revision_no: int = Field(ge=0)
    source_column: str = Field(min_length=1, max_length=200)
    master_definition_id: UUID
    master_field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    master_version: int = Field(ge=1)
    required: bool = False
    normalization: str = Field(default="TRIM_CASEFOLD", pattern=r"^[A-Z_]{3,40}$")
    cardinality: str = Field(default="MANY_TO_ONE", pattern=r"^(MANY_TO_ONE|ONE_TO_ONE)$")
    aliases: dict[str, str] = Field(default_factory=dict, max_length=200)
