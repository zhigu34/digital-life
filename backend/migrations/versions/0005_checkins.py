"""Add per-account daily/ongoing check-in items with day-unique logs."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
    op.drop_table("checkin_logs")
    op.drop_table("checkins")
