"""Business rules shared by the ledger endpoints."""

import calendar
from collections import defaultdict
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.maintenance import user_today
from app.models import Expense, LedgerAccount, LedgerCategory, LedgerEntry, LedgerPayee

# Seeded only while the user owns no category at all, so custom sets survive.
DEFAULT_CATEGORIES = {
    "expense": ["餐饮", "交通", "居住", "购物", "医疗", "学习", "娱乐", "人情", "其他"],
    "income": ["工资", "奖金", "理财", "兼职", "报销", "其他"],
}


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def months_before(day: date, months: int) -> date:
    """The same day-of-month `months` earlier, clamped into the shorter month."""
    index = day.year * 12 + day.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def payee_key(name: str) -> str:
    """Fold case and surrounding space so the dictionary cannot hold near-duplicates."""
    return name.strip().casefold()


def _owned(db: Session, model, item_id: int, user_id: int, message: str):
    record = db.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if record is None:
        raise HTTPException(404, message)
    return record


def owned_account(db: Session, item_id: int, user_id: int) -> LedgerAccount:
    return _owned(db, LedgerAccount, item_id, user_id, "账户不存在")


def owned_category(db: Session, item_id: int, user_id: int) -> LedgerCategory:
    return _owned(db, LedgerCategory, item_id, user_id, "分类不存在")


def owned_payee(db: Session, item_id: int, user_id: int) -> LedgerPayee:
    return _owned(db, LedgerPayee, item_id, user_id, "商户不存在")


def owned_entry(db: Session, item_id: int, user_id: int) -> LedgerEntry:
    return _owned(db, LedgerEntry, item_id, user_id, "流水不存在")


def account_deltas(db: Session, user_id: int) -> dict[int, int]:
    """Net movement per account, aggregated in SQL so large ledgers stay cheap."""
    totals: dict[int, int] = defaultdict(int)
    statements = (
        select(
            LedgerEntry.account_id,
            func.sum(
                case(
                    (LedgerEntry.kind == "income", LedgerEntry.amount_cents),
                    else_=-LedgerEntry.amount_cents,
                )
            ),
        )
        .where(
            LedgerEntry.user_id == user_id,
            LedgerEntry.account_id.is_not(None),
            LedgerEntry.kind.in_(("income", "expense")),
        )
        .group_by(LedgerEntry.account_id),
        select(LedgerEntry.from_account_id, func.sum(-LedgerEntry.amount_cents))
        .where(
            LedgerEntry.user_id == user_id,
            LedgerEntry.kind == "transfer",
            LedgerEntry.from_account_id.is_not(None),
        )
        .group_by(LedgerEntry.from_account_id),
        select(LedgerEntry.to_account_id, func.sum(LedgerEntry.amount_cents))
        .where(
            LedgerEntry.user_id == user_id,
            LedgerEntry.kind == "transfer",
            LedgerEntry.to_account_id.is_not(None),
        )
        .group_by(LedgerEntry.to_account_id),
    )
    for statement in statements:
        for account_id, delta in db.execute(statement).all():
            totals[account_id] += delta or 0
    return totals


def account_balances(db: Session, user_id: int) -> dict[int, int]:
    """Derived balances; storing a balance column would drift out of sync."""
    deltas = account_deltas(db, user_id)
    accounts = db.scalars(select(LedgerAccount).where(LedgerAccount.user_id == user_id)).all()
    return {item.id: item.opening_balance_cents + deltas.get(item.id, 0) for item in accounts}


def ensure_default_categories(db: Session, user_id: int) -> None:
    existing = db.scalar(
        select(func.count()).select_from(LedgerCategory).where(LedgerCategory.user_id == user_id)
    )
    if existing:
        return
    created = now()
    db.add_all(
        LedgerCategory(user_id=user_id, name=name, kind=kind, sort_order=index, created_at=created)
        for kind, names in DEFAULT_CATEGORIES.items()
        for index, name in enumerate(names, start=1)
    )
    try:
        db.commit()
    except IntegrityError:
        # A concurrent first visit already seeded the same set.
        db.rollback()


def _in_use(db: Session, statement) -> bool:
    return bool(db.scalar(statement))


def account_in_use(db: Session, account_id: int) -> bool:
    return _in_use(
        db,
        select(func.count())
        .select_from(LedgerEntry)
        .where(
            or_(
                LedgerEntry.account_id == account_id,
                LedgerEntry.from_account_id == account_id,
                LedgerEntry.to_account_id == account_id,
            )
        ),
    ) or _in_use(
        db, select(func.count()).select_from(Expense).where(Expense.account_id == account_id)
    )


def category_in_use(db: Session, category_id: int) -> bool:
    return _in_use(
        db,
        select(func.count()).select_from(LedgerEntry).where(LedgerEntry.category_id == category_id),
    ) or _in_use(
        db, select(func.count()).select_from(Expense).where(Expense.category_id == category_id)
    )


def payee_in_use(db: Session, payee_id: int) -> bool:
    return _in_use(
        db, select(func.count()).select_from(LedgerEntry).where(LedgerEntry.payee_id == payee_id)
    ) or _in_use(db, select(func.count()).select_from(Expense).where(Expense.payee_id == payee_id))


def merge_payees(db: Session, source: LedgerPayee, target: LedgerPayee) -> dict[str, int]:
    """Re-point every reference inside one transaction, then drop the source."""
    options = {"synchronize_session": False}
    entries = db.execute(
        update(LedgerEntry)
        .where(LedgerEntry.payee_id == source.id)
        .values(payee_id=target.id)
        .execution_options(**options)
    ).rowcount
    expenses = db.execute(
        update(Expense)
        .where(Expense.payee_id == source.id)
        .values(payee_id=target.id)
        .execution_options(**options)
    ).rowcount
    db.delete(source)
    db.commit()
    return {"entries": entries or 0, "expenses": expenses or 0}


def check_entry_date(occurred_on: date, timezone: str) -> None:
    if occurred_on > user_today(timezone):
        raise HTTPException(422, "日期不能晚于当前时区的今天")


def validate_entry_references(db: Session, user_id: int, values: dict) -> None:
    """Ownership and cross-record rules that need the database to decide."""
    accounts = {}
    for key in ("account_id", "from_account_id", "to_account_id"):
        account_id = values.get(key)
        if not account_id or account_id in accounts:
            continue
        account = db.scalar(
            select(LedgerAccount).where(
                LedgerAccount.id == account_id, LedgerAccount.user_id == user_id
            )
        )
        if account is None:
            raise HTTPException(422, "账户不存在")
        accounts[account_id] = account

    if values["kind"] == "transfer":
        source = accounts[values["from_account_id"]]
        target = accounts[values["to_account_id"]]
        if source.currency != target.currency:
            raise HTTPException(422, "转出与转入账户的币种必须一致")
        expected = source.currency
    else:
        expected = accounts[values["account_id"]].currency
    if values["currency"] != expected:
        raise HTTPException(422, "币种必须与账户币种一致")

    if values.get("category_id") is not None:
        category = db.scalar(
            select(LedgerCategory).where(
                LedgerCategory.id == values["category_id"], LedgerCategory.user_id == user_id
            )
        )
        if category is None:
            raise HTTPException(422, "分类不存在")
        if category.kind != values["kind"]:
            raise HTTPException(422, "分类类型必须与流水类型一致")

    if values.get("payee_id") is not None and not db.scalar(
        select(LedgerPayee.id).where(
            LedgerPayee.id == values["payee_id"], LedgerPayee.user_id == user_id
        )
    ):
        raise HTTPException(422, "商户不存在")
