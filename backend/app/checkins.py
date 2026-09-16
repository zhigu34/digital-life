"""Owner-scoped check-in items: daily habits and ongoing commitments."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.database import get_db
from app.maintenance import user_today
from app.models import CheckIn, CheckInLog
from app.schemas import ISODate, Notes, Payload, ResourceId, StrictBool

router = APIRouter(prefix="/api/checkins", tags=["checkins"])
DAYS_WINDOW = 400


class CheckInPayload(Payload):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    notes: Notes = ""
    kind: Literal["daily"] = "daily"
    active: StrictBool = True


class CheckInView(BaseModel):
    model_config = Payload.model_config

    id: int
    title: str
    notes: str
    kind: str
    active: bool
    created_at: datetime
    # Recent checked days, oldest first, for streak and week displays; the
    # total count covers history beyond this window.
    days: list[date]
    total_count: int


class CheckInLogView(BaseModel):
    model_config = Payload.model_config

    id: int
    checkin_id: int
    checked_on: date
    note: str
    created_at: datetime


class CheckInCheck(Payload):
    checked_on: ISODate | None = None
    note: Notes = ""


class CheckInPatch(BaseModel):
    model_config = Payload.model_config

    title: str | None = None
    notes: str | None = None
    kind: Literal["daily"] | None = None
    active: bool | None = None


def item_view(db: Session, item: CheckIn) -> CheckInView:
    recent = db.scalars(
        select(CheckInLog.checked_on)
        .where(CheckInLog.checkin_id == item.id)
        .order_by(CheckInLog.checked_on.desc())
        .limit(DAYS_WINDOW)
    ).all()
    total = db.scalar(
        select(func.count()).select_from(CheckInLog).where(CheckInLog.checkin_id == item.id)
    )
    return CheckInView(
        id=item.id,
        title=item.title,
        notes=item.notes,
        kind=item.kind,
        active=item.active,
        created_at=item.created_at,
        days=sorted(recent),
        total_count=total or 0,
    )


def owned_item(db: Session, item_id: int, user_id: int) -> CheckIn:
    item = db.scalar(select(CheckIn).where(CheckIn.id == item_id, CheckIn.user_id == user_id))
    if item is None:
        raise HTTPException(404, "打卡项目不存在")
    return item


@router.get("", response_model=list[CheckInView])
def list_items(identity: Identity = Depends(authenticated), db: Session = Depends(get_db)):
    items = db.scalars(
        select(CheckIn).where(CheckIn.user_id == identity.user.id).order_by(CheckIn.id.desc())
    ).all()
    return [item_view(db, item) for item in items]


@router.post("", response_model=CheckInView, status_code=201)
def create_item(
    payload: CheckInPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = CheckIn(
        user_id=identity.user.id,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        **payload.model_dump(),
    )
    db.add(item)
    db.commit()
    return item_view(db, item)


@router.patch("/{item_id}", response_model=CheckInView)
def update_item(
    item_id: ResourceId,
    payload: CheckInPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = owned_item(db, item_id, identity.user.id)
    values = validated_patch(CheckInPayload, item, payload)
    for key, value in values.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return item_view(db, item)


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    db.delete(owned_item(db, item_id, identity.user.id))
    db.commit()


@router.get("/{item_id}/logs", response_model=list[CheckInLogView])
def item_logs(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = owned_item(db, item_id, identity.user.id)
    return db.scalars(
        select(CheckInLog)
        .where(CheckInLog.checkin_id == item.id)
        .order_by(CheckInLog.checked_on.desc(), CheckInLog.id.desc())
    ).all()


@router.post("/{item_id}/check", response_model=CheckInView, status_code=201)
def check(
    item_id: ResourceId,
    payload: CheckInCheck,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = owned_item(db, item_id, identity.user.id)
    if not item.active:
        raise HTTPException(400, "已归档的打卡项目不能打卡")
    checked_on = payload.checked_on or user_today(identity.user.timezone)
    if checked_on > user_today(identity.user.timezone):
        raise HTTPException(422, "打卡日期不能晚于当前时区的今天")
    db.add(
        CheckInLog(
            checkin_id=item.id,
            checked_on=checked_on,
            note=payload.note,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "这一天已经打过卡了") from None
    return item_view(db, item)


@router.delete("/{item_id}/check/{checked_on}", status_code=204)
def undo_check(
    item_id: ResourceId,
    checked_on: date,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    item = owned_item(db, item_id, identity.user.id)
    log = db.scalar(
        select(CheckInLog).where(
            CheckInLog.checkin_id == item.id, CheckInLog.checked_on == checked_on
        )
    )
    if log is None:
        raise HTTPException(404, "这一天没有打卡记录")
    db.delete(log)
    db.commit()
