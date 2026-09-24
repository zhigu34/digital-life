"""Replace an account's life data from a personal JSON export."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated
from app.database import get_db
from app.maintenance import calculated_due
from app.maintenance_schemas import MaintenanceCreate, MaintenanceLogView
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
    ExpensePayload,
    ISODate,
    MilestonePayload,
    NotePayload,
    Notes,
    ProjectPayload,
    TaskPayload,
)
from app.shows.schemas import ShowPayload

router = APIRouter(prefix="/api", tags=["import"])
MAX_PER_COLLECTION = 10_000
MAX_TOTAL = 50_000


# Export rows also carry server-assigned fields (id, created_at, next_due);
# importing re-assigns all ids, so unknown keys are ignored per row.
IGNORE_EXTRA = ConfigDict(extra="ignore")


class TaskRow(TaskPayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class ExpenseRow(ExpensePayload):
    model_config = IGNORE_EXTRA


class ShowRow(ShowPayload):
    model_config = IGNORE_EXTRA


class MilestoneRow(MilestonePayload):
    model_config = IGNORE_EXTRA


class NoteRow(NotePayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class MaintenanceRow(MaintenanceCreate):
    model_config = IGNORE_EXTRA


class MaintenanceLogRow(MaintenanceLogView):
    model_config = IGNORE_EXTRA


class CheckInRow(BaseModel):
    model_config = IGNORE_EXTRA
    title: str = Field(min_length=1, max_length=120)
    notes: Notes = ""
    kind: Literal["daily", "ongoing"]
    active: bool = True
    created_at: datetime | None = None


class ProjectRow(ProjectPayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class CheckInLogRow(BaseModel):
    model_config = IGNORE_EXTRA
    checkin_id: int
    checked_on: ISODate
    note: Notes = ""
    created_at: datetime | None = None


COLLECTION_ROWS = {
    "tasks": TaskRow,
    "expenses": ExpenseRow,
    "shows": ShowRow,
    "milestones": MilestoneRow,
    "notes": NoteRow,
    "projects": ProjectRow,
}
MODELS = {
    "tasks": Task,
    "expenses": Expense,
    "shows": Show,
    "milestones": Milestone,
    "notes": Note,
    "projects": Project,
}


def parse_rows(payload, key, row_model):
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        raise HTTPException(422, f"{key} 应为列表")
    if len(raw) > MAX_PER_COLLECTION:
        raise HTTPException(422, f"{key} 记录数超出导入上限")
    rows = []
    for index, item in enumerate(raw, 1):
        try:
            rows.append(row_model.model_validate(item))
        except Exception as error:
            detail = str(error).split("\n", 1)[0]
            raise HTTPException(422, f"{key} 第 {index} 条记录无效：{detail}") from None
    return rows


def read_export_ids(payload, key):
    raw_ids = []
    for index, item in enumerate(payload.get(key, []), 1):
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, int):
            raise HTTPException(422, f"{key} 第 {index} 条缺少 id")
        raw_ids.append(item_id)
    if len(set(raw_ids)) != len(raw_ids):
        raise HTTPException(422, f"{key} 存在重复 id")
    return raw_ids


@router.post("/import")
def import_data(
    payload: dict,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    if not isinstance(payload, dict) or not isinstance(payload.get("user"), dict):
        raise HTTPException(422, "这不是 digital-life 导出的 JSON 文件")
    collections = {
        key: parse_rows(payload, key, row_model) for key, row_model in COLLECTION_ROWS.items()
    }
    maintenance_rows = parse_rows(payload, "maintenance", MaintenanceRow)
    log_rows = parse_rows(payload, "maintenance_logs", MaintenanceLogRow)
    checkin_rows = parse_rows(payload, "checkins", CheckInRow)
    checkin_log_rows = parse_rows(payload, "checkin_logs", CheckInLogRow)
    total = (
        sum(len(rows) for rows in collections.values())
        + len(maintenance_rows)
        + len(log_rows)
        + len(checkin_rows)
        + len(checkin_log_rows)
    )
    if total > MAX_TOTAL:
        raise HTTPException(422, "导入记录总数超出上限")
    if (
        not any(len(rows) for rows in collections.values())
        and not maintenance_rows
        and not checkin_rows
    ):
        raise HTTPException(422, "文件里没有任何生活记录")
    raw_ids = read_export_ids(payload, "maintenance")
    checkin_ids = read_export_ids(payload, "checkins")

    logs_by_item = {}
    for index, log in enumerate(log_rows, 1):
        if log.maintenance_id not in raw_ids:
            raise HTTPException(422, f"maintenance_logs 第 {index} 条引用了不存在的事项")
        seen = logs_by_item.setdefault(log.maintenance_id, {})
        if log.completed_on in seen:
            raise HTTPException(422, "导入的完成历史中存在同一天重复记录")
        seen[log.completed_on] = log

    checkin_logs_by_item = {}
    for index, log in enumerate(checkin_log_rows, 1):
        if log.checkin_id not in checkin_ids:
            raise HTTPException(422, f"checkin_logs 第 {index} 条引用了不存在的打卡项目")
        seen = checkin_logs_by_item.setdefault(log.checkin_id, {})
        if log.checked_on in seen:
            raise HTTPException(422, "导入的打卡记录中存在同一天重复")
        seen[log.checked_on] = log

    # Older exports mixed "ongoing" items into check-ins; they become
    # projects now, with their day logs summarized into notes.
    kept_checkins = []
    converted_projects = []
    for item_id, row in zip(checkin_ids, checkin_rows, strict=True):
        if row.kind == "daily":
            kept_checkins.append((item_id, row))
            continue
        notes = row.notes
        days = sorted(checkin_logs_by_item.get(item_id, {}))
        if days:
            summary = f"原打卡 {len(days)} 条（{days[0]} ~ {days[-1]}）"
            notes = f"{notes}\n{summary}" if notes else summary
        converted_projects.append((row, notes))

    user_id = identity.user.id
    db.execute(
        delete(MaintenanceLog).where(
            MaintenanceLog.maintenance_id.in_(
                select(Maintenance.id).where(Maintenance.user_id == user_id)
            )
        )
    )
    db.execute(
        delete(CheckInLog).where(
            CheckInLog.checkin_id.in_(select(CheckIn.id).where(CheckIn.user_id == user_id))
        )
    )
    for model in (Maintenance, CheckIn, Project, Task, Expense, Show, Milestone, Note):
        db.execute(delete(model).where(model.user_id == user_id))

    for key, rows in collections.items():
        model = MODELS[key]
        for row in rows:
            values = row.model_dump()
            if model in (Task, Note, Project):
                values["created_at"] = row.created_at or datetime.now(UTC).replace(tzinfo=None)
            db.add(model(user_id=user_id, **values))

    for row, notes in converted_projects:
        db.add(
            Project(
                user_id=user_id,
                title=row.title,
                notes=notes,
                status="active" if row.active else "paused",
                created_at=row.created_at or datetime.now(UTC).replace(tzinfo=None),
            )
        )

    imported_logs = 0
    for item_id, row in zip(raw_ids, maintenance_rows, strict=True):
        logs = logs_by_item.get(item_id) or {
            row.last_completed: MaintenanceLogRow(
                maintenance_id=item_id, completed_on=row.last_completed
            )
        }
        latest = max(logs)
        item = Maintenance(
            user_id=user_id,
            last_completed=latest,
            next_due=calculated_due(latest, row.period_value, row.period_unit),
            **row.model_dump(exclude={"last_completed"}),
        )
        db.add(item)
        db.flush()
        for completed_on, log in logs.items():
            db.add(
                MaintenanceLog(
                    maintenance_id=item.id,
                    completed_on=completed_on,
                    notes=log.notes,
                    cost_cents=log.cost_cents,
                    currency=log.currency,
                    created_at=log.created_at or datetime.now(UTC).replace(tzinfo=None),
                )
            )
            imported_logs += 1
    imported_checkin_logs = 0
    for item_id, row in kept_checkins:
        item = CheckIn(
            user_id=user_id,
            created_at=row.created_at or datetime.now(UTC).replace(tzinfo=None),
            **row.model_dump(exclude={"created_at"}),
        )
        db.add(item)
        db.flush()
        for log in (checkin_logs_by_item.get(item_id) or {}).values():
            db.add(
                CheckInLog(
                    checkin_id=item.id,
                    checked_on=log.checked_on,
                    note=log.note,
                    created_at=log.created_at or datetime.now(UTC).replace(tzinfo=None),
                )
            )
            imported_checkin_logs += 1
    db.commit()
    return {
        "imported": {
            "tasks": len(collections["tasks"]),
            "expenses": len(collections["expenses"]),
            "shows": len(collections["shows"]),
            "milestones": len(collections["milestones"]),
            "notes": len(collections["notes"]),
            "maintenance": len(maintenance_rows),
            "maintenance_logs": imported_logs,
            "checkins": len(kept_checkins),
            "checkin_logs": imported_checkin_logs,
            "projects": len(collections["projects"]) + len(converted_projects),
        }
    }
