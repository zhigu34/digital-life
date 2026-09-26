"""Request and response models for long-term task groups."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas import ISODate, Notes, Payload, StrictBool

# A period is satisfied by any completion inside it, so there is no schedule to
# describe: day = today, week = Monday..Sunday, month = the calendar month.
RepeatUnit = Literal["day", "week", "month"]
GroupTitle = Annotated[str, Field(min_length=1, max_length=120)]


class ItemPayload(Payload):
    title: GroupTitle
    repeat_unit: RepeatUnit = "day"
    # Defaults to the user's today; earlier days were never expected.
    start_date: ISODate | None = None


class ItemPatch(Payload):
    title: GroupTitle | None = None
    repeat_unit: RepeatUnit | None = None
    start_date: ISODate | None = None


class ItemView(BaseModel):
    model_config = Payload.model_config

    id: int
    group_id: int
    title: str
    repeat_unit: RepeatUnit
    start_date: date
    created_at: datetime
    # Recent completion days, oldest first, for the period grids; total_count
    # covers everything ever recorded, including days outside the window.
    recent_days: list[date]
    total_count: int


class GroupCreate(Payload):
    title: GroupTitle
    notes: Notes = ""
    # At least one item: a group without items would never show anything.
    items: Annotated[list[ItemPayload], Field(min_length=1, max_length=50)]


class GroupPatch(Payload):
    title: GroupTitle | None = None
    notes: Notes | None = None
    archived: StrictBool | None = None


class GroupView(BaseModel):
    model_config = Payload.model_config

    id: int
    title: str
    notes: str
    archived: bool
    archived_on: date | None
    created_at: datetime
    items: list[ItemView]


class CompletionPayload(Payload):
    on: ISODate | None = None
    note: Notes = ""


class CompletionView(BaseModel):
    model_config = Payload.model_config

    id: int
    item_id: int
    completed_on: date
    note: str
    created_at: datetime


class GroupLogView(CompletionView):
    """A completion plus the item it belongs to, for the group's activity log."""

    item_title: str
