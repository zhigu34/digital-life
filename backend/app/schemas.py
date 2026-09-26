import re
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import Path
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    create_model,
    field_validator,
    model_validator,
)

from app.timezones import validate_timezone


def iso_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Date must be YYYY-MM-DD")
    return value


ISODate = Annotated[date, BeforeValidator(iso_date)]
ResourceId = Annotated[int, Path(ge=1, le=2**63 - 1)]


def integer_period(value):
    if type(value) is not int:
        raise ValueError("Period must be an integer")
    return value


Period = Annotated[Literal[1, 3, 12], BeforeValidator(integer_period)]
Username = Annotated[str, Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]
Password = Annotated[str, Field(min_length=12, max_length=128)]
DisplayName = Annotated[str, Field(min_length=1, max_length=60)]
Notes = Annotated[str, Field(max_length=4000)]
StrictInt = Annotated[int, Field(strict=True)]
StrictBool = Annotated[bool, Field(strict=True)]
Theme = Literal["light", "dark", "system"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


def patch_schema(name, schema):
    return create_model(
        name,
        __base__=Payload,
        **{
            key: (field.rebuild_annotation() | None, None)
            for key, field in schema.model_fields.items()
        },
    )


class Profile(Payload):
    display_name: DisplayName
    birthday: ISODate | None = None
    timezone: str = "Asia/Shanghai"
    theme: Theme = "light"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        return validate_timezone(value)


class UserView(Payload):
    display_name: DisplayName
    birthday: ISODate | None = None
    timezone: str
    theme: Theme
    id: int
    username: str
    is_admin: bool
    is_active: bool


class Login(Payload):
    username: Annotated[str, Field(min_length=1, max_length=128)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class PasswordChange(Payload):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password


class UserCreate(Payload):
    username: Username
    password: Password
    display_name: DisplayName


class AdminUpdate(Payload):
    display_name: DisplayName | None = None
    is_active: StrictBool | None = None
    password: Password | None = None

    @field_validator("display_name", "is_active", "password", mode="before")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class TaskPayload(Payload):
    title: Annotated[str, Field(min_length=1, max_length=160)]
    notes: Notes = ""
    status: Literal["todo", "doing", "waiting", "done"] = "todo"
    due_date: ISODate | None = None
    priority: Literal["low", "normal", "high"] = "normal"


class TaskView(TaskPayload):
    id: int
    created_at: datetime
    # Server-derived from `status`; deliberately absent from TaskPayload so a
    # client can never set a completion date of its own choosing.
    completed_on: date | None = None


class ExpensePayload(Payload):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    amount_cents: Annotated[StrictInt, Field(ge=1, le=100000000)]
    currency: Literal["CNY", "USD", "EUR", "JPY", "HKD"] = "CNY"
    period_months: Period = 1
    next_due: ISODate
    anchor_day: Annotated[StrictInt, Field(ge=1, le=31)] | None = None
    active: StrictBool = True
    notes: Notes = ""
    # Optional ledger defaults used only when confirming the bill as paid; older
    # rows stay null and nothing is generated for them.
    account_id: Annotated[StrictInt, Field(ge=1, le=2**63 - 1)] | None = None
    category_id: Annotated[StrictInt, Field(ge=1, le=2**63 - 1)] | None = None
    payee_id: Annotated[StrictInt, Field(ge=1, le=2**63 - 1)] | None = None
    book_id: Annotated[StrictInt, Field(ge=1, le=2**63 - 1)] | None = None

    @field_validator("anchor_day", mode="before")
    @classmethod
    def anchor_not_null(cls, value):
        if value is None:
            raise ValueError("Anchor day cannot be null")
        return value

    @model_validator(mode="after")
    def default_anchor(self):
        if self.anchor_day is None:
            self.anchor_day = self.next_due.day
        return self


class ExpenseView(ExpensePayload):
    id: int


class ExpensePayView(ExpenseView):
    """`/pay` answer: the bill plus the entry it generated, when it generated one."""

    entry_id: int | None = None


class MilestonePayload(Payload):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    date: ISODate
    repeats_yearly: StrictBool = False
    notes: Notes = ""


class MilestoneView(MilestonePayload):
    id: int


class ProjectPayload(Payload):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    notes: Notes = ""
    status: Literal["active", "paused", "done"] = "active"


class ProjectView(ProjectPayload):
    id: int
    created_at: datetime


class NotePayload(Payload):
    content: Annotated[str, Field(min_length=1, max_length=4000)]
    entry_date: ISODate


class NoteView(NotePayload):
    id: int
    created_at: datetime


ProfilePatch = patch_schema("ProfilePatch", Profile)
TaskPatch = patch_schema("TaskPatch", TaskPayload)
ExpensePatch = patch_schema("ExpensePatch", ExpensePayload)
MilestonePatch = patch_schema("MilestonePatch", MilestonePayload)
NotePatch = patch_schema("NotePatch", NotePayload)
ProjectPatch = patch_schema("ProjectPatch", ProjectPayload)
