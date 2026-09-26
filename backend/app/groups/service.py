"""Ownership lookups and derived views for long-term task groups."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.groups.schemas import CompletionView, GroupLogView, GroupView, ItemView
from app.models import TaskCompletion, TaskGroup, TaskGroupItem

# Same window the check-in list used: enough history for streaks and grids while
# keeping every list response bounded. Older completions stay reachable through
# the per-item range endpoint.
DAYS_WINDOW = 400
# A single range request covers a year plus a leap day.
MAX_SPAN_DAYS = 366


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def owned_group(db: Session, group_id: int, user_id: int) -> TaskGroup:
    group = db.scalar(
        select(TaskGroup).where(TaskGroup.id == group_id, TaskGroup.user_id == user_id)
    )
    if group is None:
        raise HTTPException(404, "长期任务不存在")
    return group


def owned_item(db: Session, group: TaskGroup, item_id: int) -> TaskGroupItem:
    """Resolve an item only through its group, so a foreign item answers 404."""
    item = db.scalar(
        select(TaskGroupItem).where(TaskGroupItem.id == item_id, TaskGroupItem.group_id == group.id)
    )
    if item is None:
        raise HTTPException(404, "打卡项不存在")
    return item


def validate_span(start: date, end: date):
    if end < start:
        raise HTTPException(422, "结束日期不能早于开始日期")
    if (end - start).days > MAX_SPAN_DAYS:
        raise HTTPException(422, "一次最多查询一年的记录")


def item_view(item: TaskGroupItem, days: list[date], total: int) -> ItemView:
    return ItemView(
        id=item.id,
        group_id=item.group_id,
        title=item.title,
        repeat_unit=item.repeat_unit,
        start_date=item.start_date,
        created_at=item.created_at,
        recent_days=sorted(days),
        total_count=total,
    )


def _windows(db: Session, item_ids: list[int], today: date):
    """Completion days (bounded) and lifetime counts for many items at once."""
    days: dict[int, list[date]] = defaultdict(list)
    counts: dict[int, int] = {}
    if not item_ids:
        return days, counts
    since = today - timedelta(days=DAYS_WINDOW)
    for item_id, completed_on in db.execute(
        select(TaskCompletion.item_id, TaskCompletion.completed_on)
        .where(TaskCompletion.item_id.in_(item_ids), TaskCompletion.completed_on >= since)
        .order_by(TaskCompletion.item_id, TaskCompletion.completed_on)
    ).all():
        days[item_id].append(completed_on)
    for item_id, count in db.execute(
        select(TaskCompletion.item_id, func.count())
        .where(TaskCompletion.item_id.in_(item_ids))
        .group_by(TaskCompletion.item_id)
    ).all():
        counts[item_id] = count
    return days, counts


def group_view(db: Session, group: TaskGroup, today: date) -> GroupView:
    return groups_view(db, [group], today)[0]


def groups_view(db: Session, groups: list[TaskGroup], today: date) -> list[GroupView]:
    """Build every group view with a fixed number of queries (no per-group one)."""
    if not groups:
        return []
    items = db.scalars(
        select(TaskGroupItem)
        .where(TaskGroupItem.group_id.in_([group.id for group in groups]))
        .order_by(TaskGroupItem.id)
    ).all()
    days, counts = _windows(db, [item.id for item in items], today)
    by_group: dict[int, list[ItemView]] = defaultdict(list)
    for item in items:
        by_group[item.group_id].append(item_view(item, days[item.id], counts.get(item.id, 0)))
    return [
        GroupView(
            id=group.id,
            title=group.title,
            notes=group.notes,
            archived=group.archived,
            archived_on=group.archived_on,
            created_at=group.created_at,
            items=by_group[group.id],
        )
        for group in groups
    ]


def item_response(db: Session, item: TaskGroupItem, today: date) -> ItemView:
    days, counts = _windows(db, [item.id], today)
    return item_view(item, days[item.id], counts.get(item.id, 0))


def completions_between(
    db: Session, item: TaskGroupItem, start: date, end: date
) -> list[TaskCompletion]:
    return list(
        db.scalars(
            select(TaskCompletion)
            .where(
                TaskCompletion.item_id == item.id,
                TaskCompletion.completed_on >= start,
                TaskCompletion.completed_on <= end,
            )
            .order_by(TaskCompletion.completed_on.desc(), TaskCompletion.id.desc())
        ).all()
    )


def completion_view(row: TaskCompletion) -> CompletionView:
    return CompletionView.model_validate(row)


def group_log(db: Session, group: TaskGroup, limit: int) -> list[GroupLogView]:
    """Newest completions across every item of one group.

    Loaded on demand (the UI pulls it when a card is expanded), so the list
    endpoint never carries a growing log for every group.
    """
    rows = db.execute(
        select(TaskCompletion, TaskGroupItem.title)
        .join(TaskGroupItem, TaskGroupItem.id == TaskCompletion.item_id)
        .where(TaskGroupItem.group_id == group.id)
        .order_by(TaskCompletion.completed_on.desc(), TaskCompletion.id.desc())
        .limit(limit)
    ).all()
    return [
        GroupLogView(
            id=row.id,
            item_id=row.item_id,
            item_title=title,
            completed_on=row.completed_on,
            note=row.note,
            created_at=row.created_at,
        )
        for row, title in rows
    ]


def export_groups(db: Session, user_id: int) -> dict:
    groups = db.scalars(
        select(TaskGroup).where(TaskGroup.user_id == user_id).order_by(TaskGroup.id)
    ).all()
    group_ids = [group.id for group in groups]
    items = (
        db.scalars(
            select(TaskGroupItem)
            .where(TaskGroupItem.group_id.in_(group_ids))
            .order_by(TaskGroupItem.id)
        ).all()
        if group_ids
        else []
    )
    item_ids = [item.id for item in items]
    completions = (
        db.scalars(
            select(TaskCompletion)
            .where(TaskCompletion.item_id.in_(item_ids))
            .order_by(TaskCompletion.id)
        ).all()
        if item_ids
        else []
    )
    return {
        "task_groups": [
            {
                "id": group.id,
                "title": group.title,
                "notes": group.notes,
                "archived": group.archived,
                "archived_on": group.archived_on,
                "created_at": group.created_at,
            }
            for group in groups
        ],
        "task_group_items": [
            {
                "id": item.id,
                "group_id": item.group_id,
                "title": item.title,
                "repeat_unit": item.repeat_unit,
                "start_date": item.start_date,
                "created_at": item.created_at,
            }
            for item in items
        ],
        "task_completions": [
            {
                "id": row.id,
                "item_id": row.item_id,
                "completed_on": row.completed_on,
                "note": row.note,
                "created_at": row.created_at,
            }
            for row in completions
        ],
    }
