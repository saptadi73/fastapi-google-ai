import re
from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery.schedules import crontab
from pydantic import Field, model_validator

from app.schemas.common import StrictModel
from app.schemas.data_policy import DatasetKind


class SourceAccessMetadata(StrictModel):
    owner_unit_id: UUID
    business_domain_id: UUID
    jurisdiction_id: UUID
    purpose_id: UUID
    data_owner_user_id: UUID
    data_steward_user_id: UUID
    sensitivity: Literal["LOW", "MEDIUM", "HIGH"]


class SourceAccessMetadataUpdate(StrictModel):
    revision_no: int = Field(ge=1)
    access_metadata: SourceAccessMetadata


class SourceMetadataReview(StrictModel):
    revision_no: int = Field(ge=1)
    decision: Literal["APPROVE", "REJECT"]
    reason: Literal["METADATA_VERIFIED", "SCOPE_MISMATCH", "OWNER_UNCONFIRMED", "OTHER"]

    @model_validator(mode="after")
    def reason_matches_decision(self):
        if (self.decision == "APPROVE") != (self.reason == "METADATA_VERIFIED"):
            raise ValueError("METADATA_VERIFIED hanya untuk approval; rejection memerlukan alasan lain")
        return self


class SourceAccessActivation(StrictModel):
    revision_no: int = Field(ge=1)
    policy_id: UUID


class SourceCreate(StrictModel):
    source_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    name: str = Field(min_length=1, max_length=200)
    spreadsheet_url: str = Field(min_length=5, max_length=500)
    access_metadata: SourceAccessMetadata
    description: str = Field(default="", max_length=2000)
    credential_ref: str = Field(default="default", max_length=100)
    sync_schedule: str | None = None
    schedule_timezone: str = Field(default="UTC", min_length=1, max_length=100)
    concurrency_policy: Literal["QUEUE_LATEST", "SKIP_IF_RUNNING"] = "QUEUE_LATEST"

    @model_validator(mode="after")
    def valid_schedule(self):
        validate_timezone(self.schedule_timezone)
        if self.sync_schedule:
            cron_schedule(self.sync_schedule, self.schedule_timezone)
        return self


class SourceScheduleUpdate(StrictModel):
    revision_no: int = Field(ge=1)
    sync_schedule: str | None = None
    schedule_timezone: str = Field(default="UTC", min_length=1, max_length=100)
    concurrency_policy: Literal["QUEUE_LATEST", "SKIP_IF_RUNNING"] = "QUEUE_LATEST"
    dependency_source_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def valid_schedule(self):
        validate_timezone(self.schedule_timezone)
        if self.sync_schedule:
            cron_schedule(self.sync_schedule, self.schedule_timezone)
        if len(set(self.dependency_source_ids)) != len(self.dependency_source_ids):
            raise ValueError("dependency_source_ids must be unique")
        return self


def validate_timezone(value):
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("schedule_timezone must be a valid IANA timezone") from None


def cron_schedule(value, timezone_name="UTC"):
    parts = value.split()
    if len(parts) != 5:
        raise ValueError("sync_schedule must contain five cron fields")
    return crontab(
        minute=parts[0],
        hour=parts[1],
        day_of_month=parts[2],
        month_of_year=parts[3],
        day_of_week=parts[4],
        nowfun=lambda: datetime.now(validate_timezone(timezone_name)),
    )


class SheetUpdate(StrictModel):
    range_a1: str | None = Field(default=None, pattern=r"^[A-Z]+[0-9]*:[A-Z]+[0-9]*$")
    header_row: int | None = Field(default=None, ge=1, le=100)
    data_start_row: int | None = Field(default=None, ge=2, le=1000)
    enabled: bool | None = None


class SheetClassificationUpdate(StrictModel):
    revision_no: int = Field(ge=1)
    dataset_kind: DatasetKind


class SheetWatermarkUpdate(StrictModel):
    revision_no: int = Field(ge=1)
    source_column: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["INTEGER", "DECIMAL", "DATE", "DATETIME"] | None = None

    @model_validator(mode="after")
    def complete_watermark(self):
        if (self.source_column is None) != (self.kind is None):
            raise ValueError("source_column and kind must both be set or both be null")
        return self


def spreadsheet_id(value: str) -> str:
    match = re.fullmatch(r"https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)(?:/[^\s]*)?", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{5,200}", value):
        return value
    raise ValueError("Gunakan URL Google Sheets atau spreadsheet ID yang valid.")
