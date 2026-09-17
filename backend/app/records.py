import calendar
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.database import get_db
from app.maintenance_schemas import MaintenanceLogView, MaintenanceView
from app.models import (
    CheckIn,
    CheckInLog,
    Expense,
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
    ShowView,
    TaskPatch,
    TaskPayload,
    TaskView,
    UserView,
)

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


@router.post("/expenses/{item_id}/pay", response_model=ExpenseView)
def pay_expense(
    item_id: ResourceId, identity: Identity = Depends(authenticated), db: Session = Depends(get_db)
):
    expense = owned(db, Expense, item_id, identity.user.id)
    if not expense.active:
        raise HTTPException(400, "已停用的花销不能确认付款")
    month_index = expense.next_due.year * 12 + expense.next_due.month - 1 + expense.period_months
    year, month = divmod(month_index, 12)
    if year > 9999:
        raise HTTPException(400, "日期已超出支持范围")
    month += 1
    day = min(expense.anchor_day, calendar.monthrange(year, month)[1])
    expense.next_due = date(year, month, day)
    db.commit()
    return expense


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
    return data
