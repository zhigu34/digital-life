import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas import ISODate, Notes, Payload, ResourceId, StrictInt, patch_schema

MAX_EPISODES = 1_000_000


class ShowPayload(Payload):
    title: Annotated[str, Field(min_length=1, max_length=160)]
    media_type: Literal["anime", "tv", "movie"] = "tv"
    status: Literal["planned", "watching", "completed", "paused"] = "planned"
    progress: Annotated[StrictInt, Field(ge=0, le=MAX_EPISODES)] = 0
    total: Annotated[StrictInt, Field(ge=1, le=MAX_EPISODES)] | None = None
    score: Annotated[StrictInt, Field(ge=1, le=10)] | None = None
    notes: Notes = ""
    update_weekday: Annotated[StrictInt, Field(ge=0, le=6)] | None = None
    source: Literal["bangumi", "tmdb"] | None = None
    source_id: StrictInt | None = Field(default=None, ge=1, le=2**63 - 1)
    source_url: Annotated[str, Field(max_length=500)] | None = None
    poster_path: Annotated[str, Field(max_length=500)] | None = None
    seasons: StrictInt | None = Field(default=None, ge=1, le=1000)
    air_status: Literal["airing", "ended", "upcoming", "released"] | None = None
    release_year: StrictInt | None = Field(default=None, ge=1000, le=9999)
    completed_on: ISODate | None = None

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value):
        if value is not None and not re.match(r"^https?://", value, re.IGNORECASE):
            raise ValueError("Source URL must use HTTP or HTTPS")
        return value

    @model_validator(mode="after")
    def progress_within_total(self):
        if self.total is not None and self.progress > self.total:
            raise ValueError("Progress cannot exceed total")
        return self


class ShowView(ShowPayload):
    id: int


ShowPatch = patch_schema("ShowPatch", ShowPayload)

__all__ = ["MAX_EPISODES", "ResourceId", "ShowPatch", "ShowPayload", "ShowView"]
