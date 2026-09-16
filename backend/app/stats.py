import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated
from app.database import get_db
from app.models import Expense, Maintenance, MaintenanceLog, Show

router = APIRouter(prefix="/api", tags=["stats"])
WINDOW_MONTHS = 12


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
            }
        )
    by_month = {entry["month"]: entry for entry in months}

    for expense in db.scalars(
        select(Expense).where(Expense.user_id == identity.user.id, Expense.active)
    ):
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

    summary = {status: 0 for status in ("watching", "planned", "completed", "paused")}
    summary["episodes_watched"] = 0
    for show in db.scalars(select(Show).where(Show.user_id == identity.user.id)):
        if show.status in summary:
            summary[show.status] += 1
        summary["episodes_watched"] += show.progress
    return {"months": months, "shows": summary}
