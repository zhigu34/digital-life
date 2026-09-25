import calendar
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.database import get_db
from app.ledger.schemas import ExpensePayPayload
from app.ledger.service import (
    check_entry_date,
    now,
    validate_entry_references,
    validate_expense_links,
)
from app.maintenance_schemas import MaintenanceLogView, MaintenanceView
from app.models import (
    Bookmark,
    CheckIn,
    CheckInLog,
    Expense,
    LedgerAccount,
    LedgerCategory,
    LedgerEntry,
    LedgerPayee,
    Maintenance,
    MaintenanceLog,
    Milestone,
    Note,
    Project,
    Show,
    Task,
)
from app.schemas import (
    ExpensePatch,
    ExpensePayload,
    ExpensePayView,
    ExpenseView,
    MilestonePatch,
    MilestonePayload,
    MilestoneView,
    NotePatch,
    NotePayload,
    NoteView,
    ProjectPatch,
    ProjectPayload,
    ProjectView,
    ResourceId,
    TaskPatch,
    TaskPayload,
    TaskView,
    UserView,
)
from app.shows.schemas import ShowView
from app.timezones import user_today

router = APIRouter(prefix="/api", tags=["records"])
COLLECTIONS = {
    "tasks": (Task, TaskPayload, TaskPatch, TaskView),
    "expenses": (Expense, ExpensePayload, ExpensePatch, ExpenseView),
    "milestones": (Milestone, MilestonePayload, MilestonePatch, MilestoneView),
    "notes": (Note, NotePayload, NotePatch, NoteView),
    "projects": (Project, ProjectPayload, ProjectPatch, ProjectView),
}


def owned(db, model, item_id, user_id):
    record = db.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if record is None:
        raise HTTPException(404, "记录不存在")
    return record


def register_collection(name, model, create_schema, patch_schema, view):
    def list_records(identity: Identity = Depends(authenticated), db: Session = Depends(get_db)):
        return db.scalars(
            select(model).where(model.user_id == identity.user.id).order_by(model.id.desc())
        ).all()

    def get_record(
        item_id: ResourceId,
        identity: Identity = Depends(authenticated),
        db: Session = Depends(get_db),
    ):
        return owned(db, model, item_id, identity.user.id)

    def create_record(
        payload: create_schema,
        identity: Identity = Depends(authenticated),
        db: Session = Depends(get_db),
    ):
        values = payload.model_dump()
        if model is Expense:
            validate_expense_links(db, identity.user.id, values)
        if model in (Task, Note, Project):
            values["created_at"] = datetime.now(UTC).replace(tzinfo=None)
        item = model(user_id=identity.user.id, **values)
        db.add(item)
        db.commit()
        return item

    def update_record(
        item_id: ResourceId,
        payload: patch_schema,
        identity: Identity = Depends(authenticated),
        db: Session = Depends(get_db),
    ):
        item = owned(db, model, item_id, identity.user.id)
        values = validated_patch(create_schema, item, payload).model_dump()
        if model is Expense:
            validate_expense_links(db, identity.user.id, values)
        for key, value in values.items():
            setattr(item, key, value)
        db.commit()
        return item

    def delete_record(
        item_id: ResourceId,
        identity: Identity = Depends(authenticated),
        db: Session = Depends(get_db),
    ):
        db.delete(owned(db, model, item_id, identity.user.id))
        db.commit()

    router.add_api_route(
        "/" + name, list_records, methods=["GET"], response_model=list[view], name=f"list_{name}"
    )
    router.add_api_route(
        "/" + name,
        create_record,
        methods=["POST"],
        response_model=view,
        status_code=201,
        name=f"create_{name}",
    )
    router.add_api_route(
        "/" + name + "/{item_id}",
        get_record,
        methods=["GET"],
        response_model=view,
        name=f"get_{name}",
    )
    router.add_api_route(
        "/" + name + "/{item_id}",
        update_record,
        methods=["PATCH"],
        response_model=view,
        name=f"update_{name}",
    )
    router.add_api_route(
        "/" + name + "/{item_id}",
        delete_record,
        methods=["DELETE"],
        status_code=204,
        name=f"delete_{name}",
    )


for name, definitions in COLLECTIONS.items():
    register_collection(name, *definitions)


@router.post("/expenses/{item_id}/pay", response_model=ExpensePayView)
def pay_expense(
    item_id: ResourceId,
    payload: ExpensePayPayload | None = None,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    expense = owned(db, Expense, item_id, identity.user.id)
    if not expense.active:
        raise HTTPException(400, "已停用的花销不能确认付款")
    options = payload or ExpensePayPayload()
    # Request values win; otherwise fall back to the defaults bound to the bill.
    account_id = options.account_id if options.account_id is not None else expense.account_id
    category_id = options.category_id if options.category_id is not None else expense.category_id
    payee_id = options.payee_id if options.payee_id is not None else expense.payee_id
    occurred_on = options.occurred_on or user_today(identity.user.timezone)
    check_entry_date(occurred_on, identity.user.timezone)

    entry_values = None
    if account_id is not None:
        entry_values = {
            "kind": "expense",
            "amount_cents": expense.amount_cents,
            "currency": expense.currency,
            "account_id": account_id,
            "category_id": category_id,
            "payee_id": payee_id,
        }
        # Validate before advancing the due date: a rejected link must not leave
        # a bill that moved on without recording the payment.
        validate_entry_references(db, identity.user.id, entry_values)

    month_index = expense.next_due.year * 12 + expense.next_due.month - 1 + expense.period_months
    year, month = divmod(month_index, 12)
    if year > 9999:
        raise HTTPException(400, "日期已超出支持范围")
    month += 1
    day = min(expense.anchor_day, calendar.monthrange(year, month)[1])
    expense.next_due = date(year, month, day)

    entry_id = None
    if entry_values is not None:
        entry = LedgerEntry(
            user_id=identity.user.id,
            occurred_on=occurred_on,
            note="",
            expense_id=expense.id,
            created_at=now(),
            **entry_values,
        )
        db.add(entry)
        db.flush()
        entry_id = entry.id
    db.commit()
    return ExpensePayView(**ExpenseView.model_validate(expense).model_dump(), entry_id=entry_id)


@router.get("/export")
def export_data(identity: Identity = Depends(authenticated), db: Session = Depends(get_db)):
    data = {"user": UserView.model_validate(identity.user)}
    for name, (model, _, _, view) in COLLECTIONS.items():
        data[name] = [
            view.model_validate(row)
            for row in db.scalars(
                select(model).where(model.user_id == identity.user.id).order_by(model.id)
            )
        ]
    data["shows"] = [
        ShowView.model_validate(row)
        for row in db.scalars(
            select(Show).where(Show.user_id == identity.user.id).order_by(Show.id)
        )
    ]
    data["maintenance"] = [
        MaintenanceView.model_validate(row)
        for row in db.scalars(
            select(Maintenance)
            .where(Maintenance.user_id == identity.user.id)
            .order_by(Maintenance.id)
        )
    ]
    data["maintenance_logs"] = [
        MaintenanceLogView.model_validate(row)
        for row in db.scalars(
            select(MaintenanceLog)
            .join(Maintenance)
            .where(Maintenance.user_id == identity.user.id)
            .order_by(MaintenanceLog.id)
        )
    ]
    data["checkins"] = [
        {
            "id": row.id,
            "title": row.title,
            "notes": row.notes,
            "kind": row.kind,
            "active": row.active,
            "created_at": row.created_at,
        }
        for row in db.scalars(
            select(CheckIn).where(CheckIn.user_id == identity.user.id).order_by(CheckIn.id)
        )
    ]
    data["checkin_logs"] = [
        {
            "id": row.id,
            "checkin_id": row.checkin_id,
            "checked_on": row.checked_on,
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in db.scalars(
            select(CheckInLog)
            .join(CheckIn)
            .where(CheckIn.user_id == identity.user.id)
            .order_by(CheckInLog.id)
        )
    ]

    def ledger_export(model, fields):
        return [
            {
                "id": row.id,
                "created_at": row.created_at,
                **{name: getattr(row, name) for name in fields},
            }
            for row in db.scalars(
                select(model).where(model.user_id == identity.user.id).order_by(model.id)
            )
        ]

    # Balances are derived, so they are not exported; the importer recomputes them.
    data["ledger_accounts"] = ledger_export(
        LedgerAccount,
        ("name", "kind", "currency", "opening_balance_cents", "archived", "sort_order"),
    )
    data["ledger_categories"] = ledger_export(
        LedgerCategory, ("name", "kind", "archived", "sort_order")
    )
    data["ledger_payees"] = ledger_export(LedgerPayee, ("name", "kind", "archived", "sort_order"))
    data["ledger_entries"] = ledger_export(
        LedgerEntry,
        (
            "occurred_on",
            "kind",
            "amount_cents",
            "currency",
            "account_id",
            "from_account_id",
            "to_account_id",
            "category_id",
            "payee_id",
            "note",
            "expense_id",
        ),
    )
    data["bookmarks"] = [
        {
            "id": row.id,
            "url": row.url,
            "title": row.title,
            "note": row.note,
            "folder": row.folder,
            "starred": row.starred,
            "visit_count": row.visit_count,
            "last_visited_at": row.last_visited_at,
            "created_at": row.created_at,
        }
        for row in db.scalars(
            select(Bookmark).where(Bookmark.user_id == identity.user.id).order_by(Bookmark.id)
        )
    ]
    return data
