from pydantic import Field

from app.schemas.common import StrictModel


class ResolutionRequest(StrictModel):
    resolution: str = Field(min_length=3, max_length=2000)
