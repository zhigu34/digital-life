"""Validation schemas for the ledger domain."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas import ISODate, Notes, Payload, StrictBool, StrictInt, patch_schema

Currency = Literal["CNY", "USD", "EUR", "JPY", "HKD"]
AccountKind = Literal["cash", "debit", "credit", "ewallet", "invest", "other"]
CategoryKind = Literal["income", "expense"]
PayeeKind = Literal["merchant", "org", "person"]
EntryKind = Literal["income", "expense", "transfer"]

MAX_AMOUNT_CENTS = 100_000_000
MAX_BALANCE_CENTS = 1_000_000_000
MAX_SORT_ORDER = 1000
MAX_ID = 2**63 - 1

EntryId = Annotated[StrictInt, Field(ge=1, le=MAX_ID)]
SortOrder = Annotated[StrictInt, Field(ge=0, le=MAX_SORT_ORDER)]


class AccountPayload(Payload):
    name: Annotated[str, Field(min_length=1, max_length=40)]
    kind: AccountKind = "debit"
    currency: Currency = "CNY"
    opening_balance_cents: Annotated[
        StrictInt, Field(ge=-MAX_BALANCE_CENTS, le=MAX_BALANCE_CENTS)
    ] = 0
    archived: StrictBool = False
    sort_order: SortOrder = 0

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class AccountView(AccountPayload):
    id: int
    balance_cents: int
    created_at: datetime


AccountPatch = patch_schema("AccountPatch", AccountPayload)


class CategoryPayload(Payload):
    name: Annotated[str, Field(min_length=1, max_length=20)]
    kind: CategoryKind
    archived: StrictBool = False
    sort_order: SortOrder = 0

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class CategoryView(CategoryPayload):
    id: int
    created_at: datetime


class CategoryPatch(BaseModel):
    """`kind` is deliberately absent: changing it would rewrite history."""

    model_config = Payload.model_config

    name: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    archived: StrictBool | None = None
    sort_order: SortOrder | None = None


class PayeePayload(Payload):
    name: Annotated[str, Field(min_length=1, max_length=40)]
    kind: PayeeKind = "merchant"
    archived: StrictBool = False
    sort_order: SortOrder = 0

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class PayeeView(PayeePayload):
    id: int
    created_at: datetime


PayeePatch = patch_schema("PayeePatch", PayeePayload)


class PayeeMerge(Payload):
    into: EntryId


class EntryPayload(Payload):
    occurred_on: ISODate
    kind: EntryKind
    amount_cents: Annotated[StrictInt, Field(ge=1, le=MAX_AMOUNT_CENTS)]
    currency: Currency = "CNY"
    account_id: EntryId | None = None
    from_account_id: EntryId | None = None
    to_account_id: EntryId | None = None
    category_id: EntryId | None = None
    payee_id: EntryId | None = None
    note: Notes = ""

    @model_validator(mode="after")
    def kind_matches_fields(self):
        if self.kind == "transfer":
            if self.from_account_id is None or self.to_account_id is None:
                raise ValueError("Transfer requires both source and target accounts")
            if self.from_account_id == self.to_account_id:
                raise ValueError("Transfer accounts must differ")
            if self.account_id or self.category_id or self.payee_id:
                raise ValueError("Transfer cannot carry account, category or payee")
        else:
            if self.account_id is None:
                raise ValueError("Income and expense require an account")
            if self.from_account_id is not None or self.to_account_id is not None:
                raise ValueError("Income and expense cannot carry transfer accounts")
        return self


class EntryView(EntryPayload):
    id: int
    expense_id: int | None = None
    created_at: datetime


EntryPatch = patch_schema("EntryPatch", EntryPayload)

__all__ = [
    "MAX_AMOUNT_CENTS",
    "MAX_BALANCE_CENTS",
    "MAX_ID",
    "AccountKind",
    "AccountPatch",
    "AccountPayload",
    "AccountView",
    "CategoryKind",
    "CategoryPatch",
    "CategoryPayload",
    "CategoryView",
    "Currency",
    "EntryKind",
    "EntryPatch",
    "EntryPayload",
    "EntryView",
    "PayeeKind",
    "PayeeMerge",
    "PayeePatch",
    "PayeePayload",
    "PayeeView",
]
