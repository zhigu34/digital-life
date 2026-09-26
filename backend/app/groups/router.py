"""Long-term task endpoints: groups, their check items, and daily completions."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.database import get_db
from app.groups.schemas import (
    CompletionPayload,
    CompletionView,
    GroupCreate,
    GroupPatch,
    GroupView,
    ItemPatch,
    ItemPayload,
    ItemView,
)
from app.groups.service import (
    completion_view,
    completions_between,
    group_view,
    groups_view,
    item_response,
    now,
    owned_group,
    owned_item,
    validate_span,
)
from app.models import TaskCompletion, TaskGroup, TaskGroupItem
from app.schemas import ResourceId
from app.timezones import user_today

router = APIRouter(prefix="/api/groups", tags=["groups"])


def current_day(identity: Identity) -> date:
    return user_today(identity.user.timezone)


@router.get("", response_model=list[GroupView])
def list_groups(identity: Identity = Depends(authenticated), db: Session = Depends(get_db)):
    groups = db.scalars(
        select(TaskGroup).where(TaskGroup.user_id == identity.user.id).order_by(TaskGroup.id.desc())
    ).all()
    return groups_view(db, list(groups), current_day(identity))


@router.post("", response_model=GroupView, status_code=201)
def create_group(
    payload: GroupCreate,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    today = current_day(identity)
    group = TaskGroup(
        user_id=identity.user.id,
        title=payload.title,
        notes=payload.notes,
        archived=False,
        archived_on=None,
        created_at=now(),
    )
    db.add(group)
    db.flush()
    for item in payload.items:
        db.add(
            TaskGroupItem(
                group_id=group.id,
                title=item.title,
                repeat_unit=item.repeat_unit,
                start_date=item.start_date or today,
                created_at=now(),
            )
        )
    db.commit()
    return group_view(db, group, today)


@router.get("/{group_id}", response_model=GroupView)
def get_group(
    group_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    return group_view(db, group, current_day(identity))


@router.patch("/{group_id}", response_model=GroupView)
def update_group(
    group_id: ResourceId,
    payload: GroupPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    values = validated_patch(GroupPatch, group, payload)
    for key, value in values.model_dump().items():
        # Archiving carries a date; a null in the payload never clears a field.
        if value is not None and key != "archived":
            setattr(group, key, value)
    if values.archived is not None and values.archived != group.archived:
        # Periods after the archiving day stop being expected, so re-opening a
        # group has to drop the cutoff instead of keeping a stale one.
        group.archived = values.archived
        group.archived_on = current_day(identity) if values.archived else None
    db.commit()
    return group_view(db, group, current_day(identity))


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    db.delete(owned_group(db, group_id, identity.user.id))
    db.commit()


@router.post("/{group_id}/items", response_model=ItemView, status_code=201)
def create_item(
    group_id: ResourceId,
    payload: ItemPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    today = current_day(identity)
    item = TaskGroupItem(
        group_id=group.id,
        title=payload.title,
        repeat_unit=payload.repeat_unit,
        start_date=payload.start_date or today,
        created_at=now(),
    )
    db.add(item)
    db.commit()
    return item_response(db, item, today)


@router.patch("/{group_id}/items/{item_id}", response_model=ItemView)
def update_item(
    group_id: ResourceId,
    item_id: ResourceId,
    payload: ItemPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    item = owned_item(db, group, item_id)
    values = validated_patch(ItemPatch, item, payload)
    for key, value in values.model_dump().items():
        if value is not None:
            setattr(item, key, value)
    db.commit()
    return item_response(db, item, current_day(identity))


@router.delete("/{group_id}/items/{item_id}", status_code=204)
def delete_item(
    group_id: ResourceId,
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    db.delete(owned_item(db, group, item_id))
    db.commit()


@router.post("/{group_id}/items/{item_id}/complete", response_model=ItemView, status_code=201)
def complete_item(
    group_id: ResourceId,
    item_id: ResourceId,
    payload: CompletionPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    item = owned_item(db, group, item_id)
    if group.archived:
        raise HTTPException(400, "已归档的长期任务不能打卡")
    today = current_day(identity)
    completed_on = payload.on or today
    if completed_on > today:
        raise HTTPException(422, "打卡日期不能晚于当前时区的今天")
    db.add(
        TaskCompletion(
            item_id=item.id,
            completed_on=completed_on,
            note=payload.note,
            created_at=now(),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "这一天已经打过卡了") from None
    return item_response(db, item, today)


@router.delete("/{group_id}/items/{item_id}/complete/{completed_on}", status_code=204)
def undo_completion(
    group_id: ResourceId,
    item_id: ResourceId,
    completed_on: date,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    item = owned_item(db, group, item_id)
    row = db.scalar(
        select(TaskCompletion).where(
            TaskCompletion.item_id == item.id, TaskCompletion.completed_on == completed_on
        )
    )
    if row is None:
        raise HTTPException(404, "这一天没有打卡记录")
    db.delete(row)
    db.commit()


@router.get("/{group_id}/items/{item_id}/completions", response_model=list[CompletionView])
def item_completions(
    group_id: ResourceId,
    item_id: ResourceId,
    start: date = Query(...),
    end: date = Query(...),
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    group = owned_group(db, group_id, identity.user.id)
    item = owned_item(db, group, item_id)
    validate_span(start, end)
    return [completion_view(row) for row in completions_between(db, item, start, end)]
