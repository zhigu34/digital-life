"""Initial account, session and personal collection schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(60), nullable=False),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("theme", sa.String(10), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    tables = {
        "tasks": [
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("due_date", sa.Date()),
            sa.Column("priority", sa.String(10), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        ],
        "expenses": [
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("period_months", sa.Integer(), nullable=False),
            sa.Column("next_due", sa.Date(), nullable=False),
            sa.Column("anchor_day", sa.Integer(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
        ],
        "shows": [
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("media_type", sa.String(10), nullable=False),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("progress", sa.Integer(), nullable=False),
            sa.Column("total", sa.Integer()),
            sa.Column("score", sa.Integer()),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("update_weekday", sa.Integer()),
        ],
        "milestones": [
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("repeats_yearly", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
        ],
    }
    for name, columns in tables.items():
        op.create_table(
            name,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            *columns,
        )
        op.create_index(f"ix_{name}_user_id", name, ["user_id"])


def downgrade():
    for name in ("milestones", "shows", "expenses", "tasks", "sessions", "users"):
        op.drop_table(name)
