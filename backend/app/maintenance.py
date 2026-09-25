"""Owner-scoped maintenance with an authoritative daily completion history."""

import calendar
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.database import get_db
from app.maintenance_schemas import (
    MaintenanceCompletion,
    MaintenanceConfig,
    MaintenanceCreate,
    MaintenanceLogPatch,
    MaintenanceLogView,
    MaintenancePatch,
    MaintenanceView,
)
from app.models import Maintenance, MaintenanceLog
from app.records import owned
from app.schemas import ResourceId
from app.timezones import user_today

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


def next_due_date(completed_on: date, value: int, unit: str) -> date:
    try:
        if unit == "days":
            return completed_on + timedelta(days=value)
        if unit != "months":
            raise ValueError("Unsupported maintenance period unit")
        year, month = divmod(completed_on.year * 12 + completed_on.month - 1 + value, 12)
        month += 1
        return date(year, month, min(completed_on.day, calendar.monthrange(year, month)[1]))
    except (ValueError, OverflowError):
        raise ValueError("Maintenance date is outside the supported calendar range") from None


def validate_actual_date(completed_on: date, identity: Identity):
    if completed_on > user_today(identity.user.timezone):
        raise HTTPException(422, "实际完成日期不能晚于当前时区的今天")


def calculated_due(completed_on, value, unit):
    try:
        return next_due_date(completed_on, value, unit)
    except ValueError:
        raise HTTPException(422, "下次维护日期超出支持范围，请调整周期或完成日期") from None


def save_history(db: Session, item: Maintenance):
    # get_db holds BEGIN IMMEDIATE from before authentication until this commit.
    # The database uniqueness constraint is an additional cross-process guard.
    try:
        db.flush()
        latest = db.scalar(
            select(func.max(MaintenanceLog.completed_on)).where(
                MaintenanceLog.maintenance_id == item.id
            )
        )
        item.last_completed = latest
        item.next_due = calculated_due(latest, item.period_value, item.period_unit)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "该事项在这一天已有完成记录，请编辑已有记录") from None


@router.get("", response_model=list[MaintenanceView])
def list_items(identity: Identity = Depends(authenticated), db: Session = Depends(get_db)):
    return db.scalars(
        select(Maintenance)
        .where(Maintenance.user_id == identity.user.id)
        .order_by(Maintenance.id.desc())
    ).all()


@router.post("", response_model=MaintenanceView, status_code=201)
def create_item(
    payload: MaintenanceCreate,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    validate_actual_date(payload.last_completed, identity)
    next_due = calculated_due(payload.last_completed, payload.period_value, payload.period_unit)
    item = Maintenance(user_id=identity.user.id, next_due=next_due, **payload.model_dump())
    db.add(item)
    db.flush()
    db.add(
        MaintenanceLog(
            maintenance_id=item.id,
            completed_on=payload.last_completed,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    db.commit()
    return item


@router.get("/{item_id}", response_model=MaintenanceView)
def get_item(
    item_id: ResourceId, identity: Identity = Depends(authenticated), db: Session = Depends(get_db)
):
    return owned(db, Maintenance, item_id, identity.user.id)


@router.patch("/{item_id}", response_model=MaintenanceView)
def update_item(
    item_id: ResourceId,
    payload: MaintenancePatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = owned(db, Maintenance, item_id, identity.user.id)
    values = validated_patch(MaintenanceConfig, item, payload)
    next_due = calculated_due(item.last_completed, values.period_value, values.period_unit)
    for key, value in values.model_dump().items():
        setattr(item, key, value)
    item.next_due = next_due
    db.commit()
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: ResourceId, identity: Identity = Depends(authenticated), db: Session = Depends(get_db)
):
    db.delete(owned(db, Maintenance, item_id, identity.user.id))
    db.commit()


@router.get("/{item_id}/history", response_model=list[MaintenanceLogView])
def history(
    item_id: ResourceId, identity: Identity = Depends(authenticated), db: Session = Depends(get_db)
):
    item = owned(db, Maintenance, item_id, identity.user.id)
    return db.scalars(
        select(MaintenanceLog)
        .where(MaintenanceLog.maintenance_id == item.id)
        .order_by(MaintenanceLog.completed_on.desc(), MaintenanceLog.id.desc())
    ).all()


@router.post("/{item_id}/complete", response_model=MaintenanceView, status_code=201)
def complete(
    item_id: ResourceId,
    payload: MaintenanceCompletion,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = owned(db, Maintenance, item_id, identity.user.id)
    if not item.active:
        raise HTTPException(400, "已停用的事项不能新增完成记录")
    validate_actual_date(payload.completed_on, identity)
    db.add(
        MaintenanceLog(
            maintenance_id=item.id,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            **payload.model_dump(),
        )
    )
    save_history(db, item)
    return item


@router.patch("/{item_id}/history/{log_id}", response_model=MaintenanceView)
def update_history(
    item_id: ResourceId,
    log_id: ResourceId,
    payload: MaintenanceLogPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = owned(db, Maintenance, item_id, identity.user.id)
    log = db.scalar(
        select(MaintenanceLog).where(
            MaintenanceLog.id == log_id, MaintenanceLog.maintenance_id == item.id
        )
    )
    if log is None:
        raise HTTPException(404, "完成记录不存在")
    values = validated_patch(MaintenanceCompletion, log, payload)
    validate_actual_date(values.completed_on, identity)
    for key, value in values.model_dump().items():
        setattr(log, key, value)
    save_history(db, item)
    return item
