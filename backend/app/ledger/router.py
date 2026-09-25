"""Ledger endpoints: accounts, categories, payees and entries."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.database import get_db
from app.ledger.schemas import (
    MAX_ID,
    AccountPatch,
    AccountPayload,
    AccountView,
    CategoryPatch,
    CategoryPayload,
    CategoryView,
    EntryKind,
    EntryPatch,
    EntryPayload,
    EntryView,
    PayeeMerge,
    PayeePatch,
    PayeePayload,
    PayeeView,
)
from app.ledger.service import (
    account_balances,
    account_in_use,
    category_in_use,
    check_entry_date,
    ensure_default_categories,
    merge_payees,
    months_before,
    now,
    owned_account,
    owned_category,
    owned_entry,
    owned_payee,
    payee_in_use,
    payee_key,
    validate_entry_references,
)
from app.maintenance import user_today
from app.models import LedgerAccount, LedgerCategory, LedgerEntry, LedgerPayee
from app.schemas import ResourceId

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

# Entries default to a rolling window so an old ledger cannot be dumped by one request.
ENTRY_WINDOW_MONTHS = 12
ENTRY_LIMIT_DEFAULT = 500
ENTRY_LIMIT_MAX = 2000


def account_view(account: LedgerAccount, balance: int) -> AccountView:
    return AccountView(
        id=account.id,
        name=account.name,
        kind=account.kind,
        currency=account.currency,
        opening_balance_cents=account.opening_balance_cents,
        archived=account.archived,
        sort_order=account.sort_order,
        created_at=account.created_at,
        balance_cents=balance,
    )


@router.get("/accounts", response_model=list[AccountView])
def list_accounts(identity: Identity = Depends(authenticated), db: Session = Depends(get_db)):
    balances = account_balances(db, identity.user.id)
    accounts = db.scalars(
        select(LedgerAccount)
        .where(LedgerAccount.user_id == identity.user.id)
        .order_by(LedgerAccount.sort_order, LedgerAccount.id)
    ).all()
    return [
        account_view(item, balances.get(item.id, item.opening_balance_cents)) for item in accounts
    ]


@router.post("/accounts", response_model=AccountView, status_code=201)
def create_account(
    payload: AccountPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    account = LedgerAccount(user_id=identity.user.id, created_at=now(), **payload.model_dump())
    db.add(account)
    db.commit()
    return account_view(account, account.opening_balance_cents)


@router.get("/accounts/{item_id}", response_model=AccountView)
def get_account(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    account = owned_account(db, item_id, identity.user.id)
    return account_view(account, account_balances(db, identity.user.id).get(account.id, 0))


@router.patch("/accounts/{item_id}", response_model=AccountView)
def update_account(
    item_id: ResourceId,
    payload: AccountPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    account = owned_account(db, item_id, identity.user.id)
    values = validated_patch(AccountPayload, account, payload).model_dump()
    for key, value in values.items():
        setattr(account, key, value)
    db.commit()
    return account_view(account, account_balances(db, identity.user.id).get(account.id, 0))


@router.delete("/accounts/{item_id}", status_code=204)
def delete_account(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    account = owned_account(db, item_id, identity.user.id)
    if account_in_use(db, account.id):
        raise HTTPException(409, "该账户已有流水或账单，请改为归档")
    db.delete(account)
    db.commit()


@router.get("/categories", response_model=list[CategoryView])
def list_categories(identity: Identity = Depends(authenticated), db: Session = Depends(get_db)):
    ensure_default_categories(db, identity.user.id)
    return db.scalars(
        select(LedgerCategory)
        .where(LedgerCategory.user_id == identity.user.id)
        .order_by(LedgerCategory.kind, LedgerCategory.sort_order, LedgerCategory.id)
    ).all()


@router.post("/categories", response_model=CategoryView, status_code=201)
def create_category(
    payload: CategoryPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    category = LedgerCategory(user_id=identity.user.id, created_at=now(), **payload.model_dump())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同类型下已存在同名分类") from None
    return category


@router.get("/categories/{item_id}", response_model=CategoryView)
def get_category(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    return owned_category(db, item_id, identity.user.id)


@router.patch("/categories/{item_id}", response_model=CategoryView)
def update_category(
    item_id: ResourceId,
    payload: CategoryPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    category = owned_category(db, item_id, identity.user.id)
    values = validated_patch(CategoryPayload, category, payload).model_dump()
    for key, value in values.items():
        setattr(category, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同类型下已存在同名分类") from None
    return category


@router.delete("/categories/{item_id}", status_code=204)
def delete_category(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    category = owned_category(db, item_id, identity.user.id)
    if category_in_use(db, category.id):
        raise HTTPException(409, "该分类已被流水或账单引用，请改为归档")
    db.delete(category)
    db.commit()


@router.get("/payees", response_model=list[PayeeView])
def list_payees(
    keyword: Annotated[str, Query(max_length=40)] | None = None,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    last_used = (
        select(
            LedgerEntry.payee_id.label("payee_id"),
            func.max(LedgerEntry.occurred_on).label("last_on"),
        )
        .where(LedgerEntry.user_id == identity.user.id, LedgerEntry.payee_id.is_not(None))
        .group_by(LedgerEntry.payee_id)
        .subquery()
    )
    statement = (
        select(LedgerPayee)
        .outerjoin(last_used, last_used.c.payee_id == LedgerPayee.id)
        .where(LedgerPayee.user_id == identity.user.id)
    )
    if keyword and keyword.strip():
        statement = statement.where(
            LedgerPayee.name_key.contains(payee_key(keyword), autoescape=True)
        )
    return db.scalars(
        # Recently used payees float up; never-used ones sort last in SQLite.
        statement.order_by(LedgerPayee.sort_order, last_used.c.last_on.desc(), LedgerPayee.id)
    ).all()


@router.post("/payees", response_model=PayeeView, status_code=201)
def create_payee(
    payload: PayeePayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    values = payload.model_dump()
    payee = LedgerPayee(
        user_id=identity.user.id,
        name_key=payee_key(values["name"]),
        created_at=now(),
        **values,
    )
    db.add(payee)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "已存在同名商户") from None
    return payee


@router.get("/payees/{item_id}", response_model=PayeeView)
def get_payee(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    return owned_payee(db, item_id, identity.user.id)


@router.patch("/payees/{item_id}", response_model=PayeeView)
def update_payee(
    item_id: ResourceId,
    payload: PayeePatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    payee = owned_payee(db, item_id, identity.user.id)
    values = validated_patch(PayeePayload, payee, payload).model_dump()
    for key, value in values.items():
        setattr(payee, key, value)
    payee.name_key = payee_key(payee.name)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "已存在同名商户") from None
    return payee


@router.delete("/payees/{item_id}", status_code=204)
def delete_payee(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    payee = owned_payee(db, item_id, identity.user.id)
    if payee_in_use(db, payee.id):
        raise HTTPException(409, "该商户已被流水或账单引用，请改为归档或合并")
    db.delete(payee)
    db.commit()


@router.post("/payees/{item_id}/merge")
def merge_payee(
    item_id: ResourceId,
    payload: PayeeMerge,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    source = owned_payee(db, item_id, identity.user.id)
    if payload.into == source.id:
        raise HTTPException(422, "不能合并到自身")
    target = owned_payee(db, payload.into, identity.user.id)
    return merge_payees(db, source, target)


@router.get("/entries", response_model=list[EntryView])
def list_entries(
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    kind: EntryKind | None = None,
    account_id: Annotated[int, Query(ge=1, le=MAX_ID)] | None = None,
    category_id: Annotated[int, Query(ge=1, le=MAX_ID)] | None = None,
    payee_id: Annotated[int, Query(ge=1, le=MAX_ID)] | None = None,
    limit: Annotated[int, Query(ge=1, le=ENTRY_LIMIT_MAX)] = ENTRY_LIMIT_DEFAULT,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    today = user_today(identity.user.timezone)
    end = to or today
    start = from_ or months_before(today, ENTRY_WINDOW_MONTHS)
    statement = select(LedgerEntry).where(
        LedgerEntry.user_id == identity.user.id,
        LedgerEntry.occurred_on >= start,
        LedgerEntry.occurred_on <= end,
    )
    if kind is not None:
        statement = statement.where(LedgerEntry.kind == kind)
    if account_id is not None:
        # Transfers count as activity on either side, but never as income/expense.
        statement = statement.where(
            or_(
                LedgerEntry.account_id == account_id,
                LedgerEntry.from_account_id == account_id,
                LedgerEntry.to_account_id == account_id,
            )
        )
    if category_id is not None:
        statement = statement.where(LedgerEntry.category_id == category_id)
    if payee_id is not None:
        statement = statement.where(LedgerEntry.payee_id == payee_id)
    return db.scalars(
        statement.order_by(LedgerEntry.occurred_on.desc(), LedgerEntry.id.desc()).limit(limit)
    ).all()


@router.post("/entries", response_model=EntryView, status_code=201)
def create_entry(
    payload: EntryPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    values = payload.model_dump()
    check_entry_date(values["occurred_on"], identity.user.timezone)
    validate_entry_references(db, identity.user.id, values)
    entry = LedgerEntry(user_id=identity.user.id, created_at=now(), **values)
    db.add(entry)
    db.commit()
    return entry


@router.get("/entries/{item_id}", response_model=EntryView)
def get_entry(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    return owned_entry(db, item_id, identity.user.id)


@router.patch("/entries/{item_id}", response_model=EntryView)
def update_entry(
    item_id: ResourceId,
    payload: EntryPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    entry = owned_entry(db, item_id, identity.user.id)
    values = validated_patch(EntryPayload, entry, payload).model_dump()
    check_entry_date(values["occurred_on"], identity.user.timezone)
    validate_entry_references(db, identity.user.id, values)
    for key, value in values.items():
        setattr(entry, key, value)
    db.commit()
    return entry


@router.delete("/entries/{item_id}", status_code=204)
def delete_entry(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    db.delete(owned_entry(db, item_id, identity.user.id))
    db.commit()
