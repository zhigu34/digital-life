"""Add recurring maintenance and unique daily completion history."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("period_value", sa.Integer(), nullable=False),
        sa.Column("period_unit", sa.String(6), nullable=False),
        sa.Column("remind_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_completed", sa.Date(), nullable=False),
        sa.Column("next_due", sa.Date(), nullable=False),
    )
    op.create_index("ix_maintenance_user_id", "maintenance", ["user_id"])
    op.create_table(
        "maintenance_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "maintenance_id",
            sa.Integer(),
            sa.ForeignKey("maintenance.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("cost_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("maintenance_id", "completed_on", name="uq_maintenance_logs_date"),
    )
    op.create_index("ix_maintenance_logs_maintenance_id", "maintenance_logs", ["maintenance_id"])


def downgrade():
    op.drop_table("maintenance_logs")
    op.drop_table("maintenance")
