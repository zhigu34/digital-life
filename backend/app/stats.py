import calendar
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated
from app.database import get_db
from app.ledger.schemas import MAX_ID
from app.models import (
    Expense,
    LedgerCategory,
    LedgerEntry,
    LedgerPayee,
    Maintenance,
    MaintenanceLog,
    Show,
)

router = APIRouter(prefix="/api", tags=["stats"])
WINDOW_MONTHS = 12
# Payee totals mix currencies, so the ranking uses the plain sum: exact for the
# usual single-currency ledger and stable otherwise.
UNLABELLED_PAYEE = "未标注商户"
TOP_PAYEES = 8


def parse_end_month(value: str) -> date:
    parts = value.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise HTTPException(422, "月份格式应为 YYYY-MM")
    try:
        return date(int(parts[0]), int(parts[1]), 1)
    except ValueError:
        raise HTTPException(422, "月份超出支持范围") from None


@router.get("/stats")
def statistics(
    end_month: str = Query(...),
    book_id: Annotated[int, Query(ge=1, le=MAX_ID)] | None = None,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    end = parse_end_month(end_month)
    # Month indexes are 0-based (year * 12 + month - 1) so divmod stays aligned.
    end_index = end.year * 12 + end.month - 1
    months = []
    for index in range(end_index - WINDOW_MONTHS + 1, end_index + 1):
        year, month = divmod(index, 12)
        months.append(
            {
                "month": f"{year:04d}-{month + 1:02d}",
                "expense_due": {},
                "maintenance_cost": {},
                "ledger_income": {},
                "ledger_expense": {},
            }
        )
    by_month = {entry["month"]: entry for entry in months}

    bill_conditions = [Expense.user_id == identity.user.id, Expense.active]
    if book_id is not None:
        # Projected dues follow the selected book's own bills, so a specialised
        # book never inherits the rest of the household's committed spending.
        bill_conditions.append(Expense.book_id == book_id)
    for expense in db.scalars(select(Expense).where(*bill_conditions)):
        due_index = expense.next_due.year * 12 + expense.next_due.month - 1
        for index, entry in enumerate(months, end_index - WINDOW_MONTHS + 1):
            distance = index - due_index
            # Mirror the "due this month" rule: occurrences extend in whole
            # periods from next_due without assuming payment.
            if distance >= 0 and distance % expense.period_months == 0:
                totals = entry["expense_due"]
                totals[expense.currency] = totals.get(expense.currency, 0) + expense.amount_cents

    window_start = date.fromisoformat(months[0]["month"] + "-01")
    window_end = date(end.year, end.month, calendar.monthrange(end.year, end.month)[1])
    logs = db.scalars(
        select(MaintenanceLog)
        .join(Maintenance)
        .where(
            Maintenance.user_id == identity.user.id,
            MaintenanceLog.completed_on >= window_start,
            MaintenanceLog.completed_on <= window_end,
        )
    )
    for log in logs:
        if log.cost_cents is None:
            continue
        entry = by_month[f"{log.completed_on.year:04d}-{log.completed_on.month:02d}"]
        totals = entry["maintenance_cost"]
        totals[log.currency] = totals.get(log.currency, 0) + log.cost_cents

    # Actual money moved, as opposed to the projected expense_due above. Both are
    # reported side by side; neither overwrites the other.
    month_key = f"{end.year:04d}-{end.month:02d}"
    category_totals: dict[int, dict[str, int]] = {}
    payee_totals: dict[int | None, dict[str, int]] = {}
    entry_conditions = [
        LedgerEntry.user_id == identity.user.id,
        LedgerEntry.occurred_on >= window_start,
        LedgerEntry.occurred_on <= window_end,
    ]
    if book_id is not None:
        entry_conditions.append(LedgerEntry.book_id == book_id)
    for record in db.scalars(select(LedgerEntry).where(*entry_conditions)):
        if record.kind == "transfer":
            # Moving money between own accounts is neither income nor spending.
            continue
        key = f"{record.occurred_on.year:04d}-{record.occurred_on.month:02d}"
        totals = by_month[key]["ledger_income" if record.kind == "income" else "ledger_expense"]
        totals[record.currency] = totals.get(record.currency, 0) + record.amount_cents
        if key != month_key:
            continue
        if record.category_id is not None:
            bucket = category_totals.setdefault(record.category_id, {})
            bucket[record.currency] = bucket.get(record.currency, 0) + record.amount_cents
        if record.kind == "expense":
            bucket = payee_totals.setdefault(record.payee_id, {})
            bucket[record.currency] = bucket.get(record.currency, 0) + record.amount_cents

    categories = []
    if category_totals:
        lookup = {
            row.id: row
            for row in db.scalars(
                select(LedgerCategory).where(LedgerCategory.id.in_(category_totals))
            )
        }
        for category_id, totals in category_totals.items():
            category = lookup.get(category_id)
            if category is None:
                continue
            categories.append(
                {
                    "category_id": category_id,
                    "name": category.name,
                    "kind": category.kind,
                    "totals": totals,
                }
            )
        categories.sort(key=lambda item: (item["kind"], item["name"]))

    payees = []
    if payee_totals:
        named = {payee_id for payee_id in payee_totals if payee_id is not None}
        names = (
            {
                row.id: row.name
                for row in db.scalars(select(LedgerPayee).where(LedgerPayee.id.in_(named)))
            }
            if named
            else {}
        )
        for payee_id, totals in payee_totals.items():
            name = UNLABELLED_PAYEE if payee_id is None else names.get(payee_id, UNLABELLED_PAYEE)
            payees.append({"payee_id": payee_id, "name": name, "totals": totals})
        payees.sort(key=lambda item: -sum(item["totals"].values()))
        del payees[TOP_PAYEES:]

    summary = {status: 0 for status in ("watching", "planned", "completed", "paused")}
    summary["episodes_watched"] = 0
    for show in db.scalars(select(Show).where(Show.user_id == identity.user.id)):
        if show.status in summary:
            summary[show.status] += 1
        summary["episodes_watched"] += show.progress
    return {
        "months": months,
        "shows": summary,
        "ledger": {"categories": categories, "payees": payees},
    }
