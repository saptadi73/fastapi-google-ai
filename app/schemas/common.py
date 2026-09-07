from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Envelope(BaseModel):
    status: str
    data: Any = None
    meta: dict = Field(default_factory=dict)
    errors: list[dict] = Field(default_factory=list)
