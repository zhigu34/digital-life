"""Replace check-in items with long-term task groups and periodic completions.

A long-term task is a group holding one or more check items, each with its own
period (day/week/month). The period is not a schedule of fixed dates: a week
item is satisfied by any completion inside that week, so only the completion
dates are stored and the periods are derived at read time.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _local_date(value, timezone: str):
    try:
        zone = ZoneInfo(timezone)
    except Exception:
        zone = UTC
    moment = _as_datetime(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(zone).date()


def upgrade():
    op.add_column("tasks", sa.Column("completed_on", sa.Date(), nullable=True))

    op.create_table(
        "task_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("archived_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_task_groups_user_id", "task_groups", ["user_id"])

    op.create_table(
        "task_group_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("task_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("repeat_unit", sa.String(8), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_task_group_items_group_id", "task_group_items", ["group_id"])

    op.create_table(
        "task_completions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("task_group_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("item_id", "completed_on", name="uq_task_completions_day"),
    )
    op.create_index("ix_task_completions_item_id", "task_completions", ["item_id"])

    # Every existing check-in item becomes a one-item group with a daily period.
    # Its start date is the earliest completion (never the creation timestamp):
    # a habit created on Monday and first checked on Wednesday must not gain two
    # "missed" days of history it never had.
    connection = op.get_bind()
    timezones = dict(connection.execute(sa.text("SELECT id, timezone FROM users")).fetchall())
    item_ids = {}
    for row in connection.execute(
        sa.text("SELECT id, user_id, title, notes, active, created_at FROM checkins")
    ).fetchall():
        checkin_id, user_id, title, notes, active, created_at = row
        earliest = connection.execute(
            sa.text("SELECT MIN(checked_on) FROM checkin_logs WHERE checkin_id = :checkin_id"),
            {"checkin_id": checkin_id},
        ).scalar()
        start_date = earliest or _local_date(created_at, timezones.get(user_id, "UTC"))
        group_id = connection.execute(
            sa.text(
                "INSERT INTO task_groups "
                "(user_id, title, notes, archived, archived_on, created_at) "
                "VALUES (:user_id, :title, :notes, :archived, NULL, :created_at)"
            ),
            {
                "user_id": user_id,
                "title": title,
                "notes": notes,
                "archived": 0 if active else 1,
                "created_at": created_at,
            },
        ).lastrowid
        item_ids[checkin_id] = connection.execute(
            sa.text(
                "INSERT INTO task_group_items "
                "(group_id, title, repeat_unit, start_date, created_at) "
                "VALUES (:group_id, :title, 'day', :start_date, :created_at)"
            ),
            {
                "group_id": group_id,
                "title": title,
                "start_date": start_date,
                "created_at": created_at,
            },
        ).lastrowid

    for _, checkin_id, checked_on, note, created_at in connection.execute(
        sa.text("SELECT id, checkin_id, checked_on, note, created_at FROM checkin_logs")
    ).fetchall():
        item_id = item_ids.get(checkin_id)
        if item_id is None:
            continue
        connection.execute(
            sa.text(
                "INSERT INTO task_completions (item_id, completed_on, note, created_at) "
                "VALUES (:item_id, :completed_on, :note, :created_at)"
            ),
            {
                "item_id": item_id,
                "completed_on": checked_on,
                "note": note,
                "created_at": created_at,
            },
        )

    op.drop_table("checkin_logs")
    op.drop_table("checkins")


def downgrade():
    # Best effort: the period information has no equivalent in a single check-in
    # item, so each item is written back as its own item and groups with several
    # items become several check-ins. Restoring a pre-0011 backup is the reliable
    # way back.
    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_checkins_user_id", "checkins", ["user_id"])
    op.create_table(
        "checkin_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "checkin_id",
            sa.Integer(),
            sa.ForeignKey("checkins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("checkin_id", "checked_on", name="uq_checkin_logs_day"),
    )
    op.create_index("ix_checkin_logs_checkin_id", "checkin_logs", ["checkin_id"])

    connection = op.get_bind()
    checkin_ids = {}
    for group_id, user_id, _, notes, archived, created_at in connection.execute(
        sa.text(
            "SELECT id, user_id, title, notes, archived, created_at FROM task_groups ORDER BY id"
        )
    ).fetchall():
        for item_id, item_title in connection.execute(
            sa.text(
                "SELECT id, title FROM task_group_items WHERE group_id = :group_id ORDER BY id"
            ),
            {"group_id": group_id},
        ).fetchall():
            checkin_ids[item_id] = connection.execute(
                sa.text(
                    "INSERT INTO checkins (user_id, title, notes, kind, active, created_at) "
                    "VALUES (:user_id, :title, :notes, 'daily', :active, :created_at)"
                ),
                {
                    "user_id": user_id,
                    "title": item_title,
                    "notes": notes,
                    "active": 0 if archived else 1,
                    "created_at": created_at,
                },
            ).lastrowid

    for item_id, completed_on, note, created_at in connection.execute(
        sa.text("SELECT item_id, completed_on, note, created_at FROM task_completions ORDER BY id")
    ).fetchall():
        checkin_id = checkin_ids.get(item_id)
        if checkin_id is None:
            continue
        connection.execute(
            sa.text(
                "INSERT INTO checkin_logs (checkin_id, checked_on, note, created_at) "
                "VALUES (:checkin_id, :checked_on, :note, :created_at)"
            ),
            {
                "checkin_id": checkin_id,
                "checked_on": completed_on,
                "note": note,
                "created_at": created_at,
            },
        )

    op.drop_table("task_completions")
    op.drop_table("task_group_items")
    op.drop_table("task_groups")
    op.drop_column("tasks", "completed_on")
