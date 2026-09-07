import re

from celery.schedules import crontab
from pydantic import Field, model_validator

from app.schemas.common import StrictModel


class SourceCreate(StrictModel):
    source_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    name: str = Field(min_length=1, max_length=200)
    spreadsheet_url: str = Field(min_length=5, max_length=500)
    description: str = Field(default="", max_length=2000)
    credential_ref: str = Field(default="default", max_length=100)
    sync_schedule: str | None = None

    @model_validator(mode="after")
    def valid_schedule(self):
        if self.sync_schedule:
            cron_schedule(self.sync_schedule)
        return self


def cron_schedule(value):
    parts = value.split()
    if len(parts) != 5:
        raise ValueError("sync_schedule must contain five cron fields")
    return crontab(
        minute=parts[0], hour=parts[1], day_of_month=parts[2], month_of_year=parts[3], day_of_week=parts[4]
    )


class SheetUpdate(StrictModel):
    range_a1: str | None = Field(default=None, pattern=r"^[A-Z]+[0-9]*:[A-Z]+[0-9]*$")
    header_row: int | None = Field(default=None, ge=1, le=100)
    data_start_row: int | None = Field(default=None, ge=2, le=1000)
    enabled: bool | None = None


def spreadsheet_id(value: str) -> str:
    match = re.fullmatch(r"https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)(?:/[^\s]*)?", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{5,200}", value):
        return value
    raise ValueError("Gunakan URL Google Sheets atau spreadsheet ID yang valid.")
