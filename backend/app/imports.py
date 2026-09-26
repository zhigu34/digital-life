"""Replace an account's life data from a personal JSON export."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated
from app.bookmarks.schemas import BookmarkPayload
from app.database import get_db
from app.groups.schemas import GroupTitle, RepeatUnit
from app.groups.service import now as groups_now
from app.ledger.schemas import (
    AccountPayload,
    BookPayload,
    CategoryPayload,
    EntryPayload,
    PayeePayload,
)
from app.ledger.service import DEFAULT_BOOK_NAME, now, payee_key
from app.maintenance import calculated_due
from app.maintenance_schemas import MaintenanceCreate, MaintenanceLogView
from app.models import (
    Bookmark,
    Expense,
    LedgerAccount,
    LedgerBook,
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
    TaskCompletion,
    TaskGroup,
    TaskGroupItem,
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


class TaskGroupRow(BaseModel):
    model_config = IGNORE_EXTRA
    title: GroupTitle
    notes: Notes = ""
    archived: bool = False
    archived_on: ISODate | None = None
    created_at: datetime | None = None


class TaskGroupItemRow(BaseModel):
    model_config = IGNORE_EXTRA
    group_id: int
    title: GroupTitle
    repeat_unit: RepeatUnit = "day"
    # Older or hand-written files may omit it; the earliest completion is used.
    start_date: ISODate | None = None
    created_at: datetime | None = None


class TaskCompletionRow(BaseModel):
    model_config = IGNORE_EXTRA
    item_id: int
    completed_on: ISODate
    note: Notes = ""
    created_at: datetime | None = None


class LegacyCheckInRow(BaseModel):
    """Exports written before migration 0011 carried check-in items."""

    model_config = IGNORE_EXTRA
    title: str = Field(min_length=1, max_length=120)
    notes: Notes = ""
    kind: Literal["daily", "ongoing"]
    active: bool = True
    created_at: datetime | None = None


class ProjectRow(ProjectPayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class BookmarkRow(BookmarkPayload):
    model_config = IGNORE_EXTRA
    visit_count: int = 0
    last_visited_at: datetime | None = None
    created_at: datetime | None = None


class LegacyCheckInLogRow(BaseModel):
    model_config = IGNORE_EXTRA
    checkin_id: int
    checked_on: ISODate
    note: Notes = ""
    created_at: datetime | None = None


class LedgerBookRow(BookPayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class LedgerAccountRow(AccountPayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class LedgerCategoryRow(CategoryPayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class LedgerPayeeRow(PayeePayload):
    model_config = IGNORE_EXTRA
    created_at: datetime | None = None


class LedgerEntryRow(EntryPayload):
    model_config = IGNORE_EXTRA
    # Carried in exports and re-pointed through the expense id mapping.
    expense_id: int | None = None
    created_at: datetime | None = None


COLLECTION_ROWS = {
    "tasks": TaskRow,
    "expenses": ExpenseRow,
    "shows": ShowRow,
    "milestones": MilestoneRow,
    "notes": NoteRow,
    "projects": ProjectRow,
    "bookmarks": BookmarkRow,
    "ledger_books": LedgerBookRow,
    "ledger_accounts": LedgerAccountRow,
    "ledger_categories": LedgerCategoryRow,
    "ledger_payees": LedgerPayeeRow,
    "ledger_entries": LedgerEntryRow,
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
    group_rows = parse_rows(payload, "task_groups", TaskGroupRow)
    item_rows = parse_rows(payload, "task_group_items", TaskGroupItemRow)
    completion_rows = parse_rows(payload, "task_completions", TaskCompletionRow)
    # Exports written before the long-term task merge still carry check-ins.
    # They are converted rather than rejected, so an old backup stays restorable.
    legacy_rows = parse_rows(payload, "checkins", LegacyCheckInRow)
    legacy_log_rows = parse_rows(payload, "checkin_logs", LegacyCheckInLogRow)
    total = (
        sum(len(rows) for rows in collections.values())
        + len(maintenance_rows)
        + len(log_rows)
        + len(group_rows)
        + len(item_rows)
        + len(completion_rows)
        + len(legacy_rows)
        + len(legacy_log_rows)
    )
    if total > MAX_TOTAL:
        raise HTTPException(422, "导入记录总数超出上限")
    if (
        not any(len(rows) for rows in collections.values())
        and not maintenance_rows
        and not group_rows
        and not legacy_rows
    ):
        raise HTTPException(422, "文件里没有任何生活记录")
    raw_ids = read_export_ids(payload, "maintenance")
    legacy_ids = read_export_ids(payload, "checkins")
    group_ids = read_export_ids(payload, "task_groups")
    item_ids = read_export_ids(payload, "task_group_items")
    # Ledger rows carry cross references, so every collection that can be pointed
    # at needs its old ids kept for translation. A pre-ledger export lacks these
    # keys: they parse as empty and the ledger is cleared, which is the expected
    # outcome of the replace-everything import semantics.
    book_ids = read_export_ids(payload, "ledger_books")
    account_ids = read_export_ids(payload, "ledger_accounts")
    category_ids = read_export_ids(payload, "ledger_categories")
    payee_ids = read_export_ids(payload, "ledger_payees")
    expense_ids = read_export_ids(payload, "expenses")
    entry_ids = read_export_ids(payload, "ledger_entries")

    logs_by_item = {}
    for index, log in enumerate(log_rows, 1):
        if log.maintenance_id not in raw_ids:
            raise HTTPException(422, f"maintenance_logs 第 {index} 条引用了不存在的事项")
        seen = logs_by_item.setdefault(log.maintenance_id, {})
        if log.completed_on in seen:
            raise HTTPException(422, "导入的完成历史中存在同一天重复记录")
        seen[log.completed_on] = log

    # A group without items would never show anything, and an item must belong
    # to a group in the same file: both are rejected before anything is deleted.
    items_by_group: dict[int, list[tuple[int, TaskGroupItemRow]]] = {}
    for old_item_id, item in zip(item_ids, item_rows, strict=True):
        if item.group_id not in group_ids:
            raise HTTPException(422, "task_group_items 引用了不存在的长期任务")
        items_by_group.setdefault(item.group_id, []).append((old_item_id, item))
    for group_id in group_ids:
        if not items_by_group.get(group_id):
            raise HTTPException(422, "导入的长期任务缺少打卡项")

    completions_by_item: dict[int, dict[date, TaskCompletionRow]] = {}
    for index, row in enumerate(completion_rows, 1):
        if row.item_id not in item_ids:
            raise HTTPException(422, f"task_completions 第 {index} 条引用了不存在的打卡项")
        seen = completions_by_item.setdefault(row.item_id, {})
        if row.completed_on in seen:
            raise HTTPException(422, "导入的打卡记录中存在同一天重复")
        seen[row.completed_on] = row

    legacy_logs_by_item: dict[int, dict[date, LegacyCheckInLogRow]] = {}
    for index, log in enumerate(legacy_log_rows, 1):
        if log.checkin_id not in legacy_ids:
            raise HTTPException(422, f"checkin_logs 第 {index} 条引用了不存在的打卡项目")
        seen = legacy_logs_by_item.setdefault(log.checkin_id, {})
        if log.checked_on in seen:
            raise HTTPException(422, "导入的打卡记录中存在同一天重复")
        seen[log.checked_on] = log

    # Older exports mixed "ongoing" items into check-ins; they stay projects,
    # with their day logs summarized into notes. Daily items become one-item
    # groups with a daily period, exactly like migration 0011 does.
    kept_checkins = []
    converted_projects = []
    for item_id, row in zip(legacy_ids, legacy_rows, strict=True):
        if row.kind == "daily":
            kept_checkins.append((item_id, row))
            continue
        notes = row.notes
        days = sorted(legacy_logs_by_item.get(item_id, {}))
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
    for model in (
        LedgerEntry,
        LedgerAccount,
        LedgerCategory,
        LedgerPayee,
        LedgerBook,
        Maintenance,
        # Deleting a group cascades to its items and their completions.
        TaskGroup,
        Project,
        Bookmark,
        Task,
        Expense,
        Show,
        Milestone,
        Note,
    ):
        db.execute(delete(model).where(model.user_id == user_id))

    def remapped(mapping, value, key, old_id):
        if value is None:
            return None
        if value not in mapping:
            raise HTTPException(422, f"{key} 中 id={old_id} 引用了不存在的记录")
        return mapping[value]

    # A pre-books export carries no book at all, so its bills and entries would
    # land unlabelled. Create one inside this transaction instead of seeding
    # through a helper that commits: a rejected import has to leave the caller's
    # ledger exactly as it was, and a commit here would already have dropped it.
    seeded_book_id = None
    if not book_ids and (expense_ids or entry_ids):
        seeded = LedgerBook(user_id=user_id, name=DEFAULT_BOOK_NAME, created_at=now())
        db.add(seeded)
        db.flush()
        seeded_book_id = seeded.id

    # Ledger first: bills and entries point at these rows, so each old id has to
    # be translated to the one assigned here.
    book_map = {}
    for old_id, row in zip(book_ids, collections["ledger_books"], strict=True):
        item = LedgerBook(
            user_id=user_id,
            created_at=row.created_at or datetime.now(UTC).replace(tzinfo=None),
            **row.model_dump(exclude={"created_at"}),
        )
        db.add(item)
        db.flush()
        book_map[old_id] = item.id
    default_book_id = next(iter(book_map.values()), None) or seeded_book_id

    account_map = {}
    for old_id, row in zip(account_ids, collections["ledger_accounts"], strict=True):
        item = LedgerAccount(
            user_id=user_id,
            created_at=row.created_at or datetime.now(UTC).replace(tzinfo=None),
            **row.model_dump(exclude={"created_at"}),
        )
        db.add(item)
        db.flush()
        account_map[old_id] = item.id

    category_map = {}
    for old_id, row in zip(category_ids, collections["ledger_categories"], strict=True):
        item = LedgerCategory(
            user_id=user_id,
            created_at=row.created_at or datetime.now(UTC).replace(tzinfo=None),
            **row.model_dump(exclude={"created_at"}),
        )
        db.add(item)
        db.flush()
        category_map[old_id] = item.id

    # Payees fold on the normalised name, so an export holding near-duplicates
    # collapses back into a single dictionary entry.
    payee_map = {}
    payee_index = {}
    for old_id, row in zip(payee_ids, collections["ledger_payees"], strict=True):
        key = payee_key(row.name)
        existing = payee_index.get(key)
        if existing is not None:
            payee_map[old_id] = existing
            continue
        item = LedgerPayee(
            user_id=user_id,
            name_key=key,
            created_at=row.created_at or datetime.now(UTC).replace(tzinfo=None),
            **row.model_dump(exclude={"created_at"}),
        )
        db.add(item)
        db.flush()
        payee_index[key] = item.id
        payee_map[old_id] = item.id

    expense_map = {}
    for old_id, row in zip(expense_ids, collections["expenses"], strict=True):
        values = row.model_dump()
        for field, mapping in (
            ("account_id", account_map),
            ("category_id", category_map),
            ("payee_id", payee_map),
            ("book_id", book_map),
        ):
            values[field] = remapped(mapping, values.get(field), "expenses", old_id)
        values["book_id"] = values["book_id"] or default_book_id
        item = Expense(user_id=user_id, **values)
        db.add(item)
        db.flush()
        expense_map[old_id] = item.id

    for old_id, row in zip(entry_ids, collections["ledger_entries"], strict=True):
        values = row.model_dump()
        for field in ("account_id", "from_account_id", "to_account_id"):
            values[field] = remapped(account_map, values.get(field), "ledger_entries", old_id)
        for field, mapping in (
            ("category_id", category_map),
            ("payee_id", payee_map),
            ("expense_id", expense_map),
            ("book_id", book_map),
        ):
            values[field] = remapped(mapping, values.get(field), "ledger_entries", old_id)
        values["book_id"] = values["book_id"] or default_book_id
        created_at = values.pop("created_at") or datetime.now(UTC).replace(tzinfo=None)
        db.add(LedgerEntry(user_id=user_id, created_at=created_at, **values))

    for key in ("tasks", "shows", "milestones", "notes", "projects"):
        model = MODELS[key]
        for row in collections[key]:
            values = row.model_dump()
            if model in (Task, Note, Project):
                values["created_at"] = row.created_at or datetime.now(UTC).replace(tzinfo=None)
            db.add(model(user_id=user_id, **values))

    for row in collections["bookmarks"]:
        db.add(
            Bookmark(
                user_id=user_id,
                created_at=row.created_at or datetime.now(UTC).replace(tzinfo=None),
                **row.model_dump(exclude={"created_at"}),
            )
        )

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

    imported_items = 0
    imported_completions = 0
    # One fixed timestamp for rows whose export predates a field, rather than a
    # fresh call per row.
    imported_at = groups_now()

    def add_item(group_id, title, repeat_unit, start_date, created_at):
        nonlocal imported_items
        item = TaskGroupItem(
            group_id=group_id,
            title=title,
            repeat_unit=repeat_unit,
            start_date=start_date,
            created_at=created_at,
        )
        db.add(item)
        db.flush()
        imported_items += 1
        return item

    def add_completions(item_id, rows):
        nonlocal imported_completions
        for completed_on, row in sorted(rows.items()):
            db.add(
                TaskCompletion(
                    item_id=item_id,
                    completed_on=completed_on,
                    note=row.note,
                    created_at=row.created_at or imported_at,
                )
            )
            imported_completions += 1

    for old_id, row in zip(group_ids, group_rows, strict=True):
        created = row.created_at or imported_at
        group = TaskGroup(
            user_id=user_id,
            title=row.title,
            notes=row.notes,
            archived=row.archived,
            archived_on=row.archived_on,
            created_at=created,
        )
        db.add(group)
        db.flush()
        for old_item_id, item in items_by_group.get(old_id, []):
            days = sorted(completions_by_item.get(old_item_id, {}))
            item_created = item.created_at or created
            # Never later than the first completion: a period grid must not show
            # missed periods before the item could have been checked.
            start_date = item.start_date or (days[0] if days else item_created.date())
            created_item = add_item(
                group.id, item.title, item.repeat_unit, start_date, item_created
            )
            add_completions(created_item.id, completions_by_item.get(old_item_id) or {})

    for old_id, row in kept_checkins:
        days = sorted(legacy_logs_by_item.get(old_id, {}))
        created = row.created_at or imported_at
        group = TaskGroup(
            user_id=user_id,
            title=row.title,
            notes=row.notes,
            archived=not row.active,
            archived_on=None,
            created_at=created,
        )
        db.add(group)
        db.flush()
        created_item = add_item(
            group.id, row.title, "day", days[0] if days else created.date(), created
        )
        add_completions(created_item.id, legacy_logs_by_item.get(old_id) or {})

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
            "task_groups": len(group_rows) + len(kept_checkins),
            "task_group_items": imported_items,
            "task_completions": imported_completions,
            "projects": len(collections["projects"]) + len(converted_projects),
            "bookmarks": len(collections["bookmarks"]),
            "ledger_books": len(book_map),
            "ledger_accounts": len(account_map),
            "ledger_categories": len(category_map),
            "ledger_payees": len(payee_index),
            "ledger_entries": len(entry_ids),
        }
    }
